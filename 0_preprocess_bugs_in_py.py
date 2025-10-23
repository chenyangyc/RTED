import os
import json
import subprocess
from collections import defaultdict
from data.configurations import bugs_in_py_base_proj_dir, bugs_in_py_checkout_proj_dir, bugs_in_py_info_file, bugs_in_py_meta_data_dir, conda_base, code_base


def clone_all_bugsinpy_repos(bugs_in_py_base_proj_dir, info_file):
    """
    Clone all repositories from BugSinPy information file.

    :param bugs_in_py_base_proj_dir: Base directory to store all repositories.
    :param info_file: JSON file containing project and repository information.
    """
    # Load project data from JSON file
    with open(info_file, 'r') as f:
        all_data = json.load(f)
    
    # Map project names to their Git URLs
    proj_gitdir_dict = {proj_name: next(iter(all_data[proj_name].values()))['git']
                        for proj_name in all_data}

    # Clone each repository
    for proj_name, git_url in proj_gitdir_dict.items():
        single_proj_dir = os.path.join(bugs_in_py_base_proj_dir, proj_name)

        if not os.path.exists(single_proj_dir):
            try:
                subprocess.run(['git', 'clone', git_url, single_proj_dir], check=True)
                print(f"Cloned {proj_name} successfully.")
            except subprocess.CalledProcessError as e:
                print(f"Failed to clone {proj_name} from {git_url}: {e}")


def setup_all_envs(bugs_in_py_meta_data_dir, info_file):
    log_dir = f'{code_base}/data/logs/failed_envs'
    os.makedirs(log_dir, exist_ok=True)
    
    # Load project data from JSON file
    with open(info_file, 'r') as f:
        all_bug_data = json.load(f)
    
    res0 = subprocess.run(['conda', 'info', '-e'], text=True, capture_output=True, check=True)
    existing_envs = [line.split()[0] for line in res0.stdout.split('\n') if '#' not in line and line != '']
    
    for proj_name, bugs in all_bug_data.items():
        for bug_id, bug_info in bugs.items():
            py_version = bug_info['py_version']
            env_name = f'{proj_name}_{bug_id}_env'
            
            if env_name in existing_envs:
                print(f"Environment {env_name} already exists. Skipping.")
                continue
            
            try:
                res1 = subprocess.run(['conda', 'create', '-n', env_name, f'python={py_version}'], input='y\n', text=True, capture_output=True, check=True)
                output = res1.stdout + res1.stderr
                
                requirements_files = f'{bugs_in_py_meta_data_dir}/{proj_name}/{proj_name}-{bug_id}/requirements.txt'
                res2 = subprocess.run([f'{conda_base}/envs/{env_name}/bin/pip', 'install', '-r', requirements_files], capture_output=True)
                output = output+ res2.stdout.decode('utf-8') + res2.stderr.decode('utf-8')
                
                final_res = res1.returncode == 0 and res2.returncode == 0
            except subprocess.CalledProcessError as e:
                with open(f'{log_dir}/{proj_name}-{bug_id}.log', 'w') as f:
                    f.write(str(e))
                
                output = str(e.output)
                final_res = False
            
            if final_res == False:
                subprocess.run(['conda', 'remove', '-n', env_name, '--all'], input='y\n', text=True)
                with open(f'{log_dir}/{proj_name}-{bug_id}.log', 'w') as f:
                    f.write(f"Failed to create environment for {proj_name} with Python version {py_version}.")
                    f.write(output)

    
def setup_single_proj_env(py_version, proj_name, bug_id, bugs_in_py_meta_data_dir):
    log_dir = f'{code_base}/data/logs/failed_envs'
    os.makedirs(log_dir, exist_ok=True)
    
    env_name = f'{proj_name}_{bug_id}_env'
    
    res0 = subprocess.run(['conda', 'info', '-e'], text=True, capture_output=True, check=True)
    existing_envs = [line.split()[0] for line in res0.stdout.split('\n') if '#' not in line and line != '']
    
    if env_name in existing_envs:
        print(f"Environment {env_name} already exists. Skipping.")
        return True, f'{conda_base}/{env_name}/bin'
        # subprocess.run(['conda', 'remove', '-n', env_name, '--all'], input='y\n', text=True)

    try:
        res1 = subprocess.run(['conda', 'create', '-n', env_name, f'python={py_version}'], input='y\n', text=True, capture_output=True, check=True)
        output = res1.stdout + res1.stderr
        
        requirements_files = f'{bugs_in_py_meta_data_dir}/{proj_name}/{proj_name}-{bug_id}/requirements.txt'
        res2 = subprocess.run([f'{conda_base}/envs/{env_name}/bin/pip', 'install', '-r', requirements_files], capture_output=True)
        output = output+ res2.stdout.decode('utf-8') + res2.stderr.decode('utf-8')
        
        final_res = res1.returncode == 0 and res2.returncode == 0
    except subprocess.CalledProcessError as e:
        with open(f'{log_dir}/{proj_name}-{bug_id}.log', 'w') as f:
            f.write(str(e))
        
        output = str(e.output)
        final_res = False
            
    if final_res == False:
        subprocess.run(['conda', 'remove', '-n', env_name, '--all'], input='y\n', text=True)
        with open(f'{log_dir}/{proj_name}-{bug_id}.log', 'w') as f:
            f.write(f"Failed to create environment for {proj_name} with Python version {py_version}.")
            f.write(output)

    if final_res:
        if 'luigi' in proj_name:
            # 为了处理 cannot import name ‘is_typeddict‘ from ‘typing_extensions‘ 的问题
            update_cmd = 'pip install --upgrade typing_extensions'
            subprocess.run(f'conda run -n {env_name} {update_cmd}', shell=True, check=True)
            # 处理typing_extensions 升级后导致的 TypeError: entry got an unexpected parameter group 
            subprocess.run([f'conda run -n {env_name} pip install typeguard==2.12.1'], shell=True)
        
        if 'pandas' in proj_name:
            # 为了处理 setup 无法成功的问题，是 setuptools 版本过新
            # subprocess.run([f'conda run -n {env_name} pip uninstall setuptools'], input='y\n', text=True, shell=True)
            subprocess.run([f'conda run -n {env_name} pip install setuptools==58.2.0'], shell=True)
        
        if 'scapy' in proj_name:
            subprocess.run([f'conda run -n {env_name} pip install Cython==0.29.36'], shell=True)
                
    return final_res, f'{conda_base}/{env_name}/bin'



def setup_bugsinpy_bugs(bugs_in_py_base_proj_dir, bugs_in_py_checkout_proj_dir, info_file, bugs_in_py_meta_data_dir):
    """
    Set up buggy and fixed versions of projects.

    :param bugs_in_py_base_proj_dir: Directory containing cloned repositories.
    :param bugs_in_py_checkout_proj_dir: Base directory to store bug-specific versions.
    :param all_bug_data: JSON data with bug information.
    """
    # Load project data from JSON file
    with open(info_file, 'r') as f:
        all_bug_data = json.load(f)
    
    log_dir = f'{code_base}/data/logs/setup'
    os.makedirs(log_dir, exist_ok=True)
    
    for proj_name, bugs in all_bug_data.items():
        if not any([i in proj_name for i in ['spacy']]):
            continue
        
        base_proj = os.path.join(bugs_in_py_base_proj_dir, proj_name)
        if not os.path.exists(base_proj):
            print(f"Base project directory {base_proj} does not exist. Skipping {proj_name}.")
            continue

        single_proj_dir = os.path.join(bugs_in_py_checkout_proj_dir, proj_name)
        os.makedirs(single_proj_dir, exist_ok=True)

        for bug_id, bug_info in bugs.items():
            single_bug_dir = os.path.join(single_proj_dir, bug_id)
            py_version = bug_info['py_version']
            
            is_env_set, python_dir = setup_single_proj_env(py_version, proj_name, bug_id, bugs_in_py_meta_data_dir)
            
            if not is_env_set:
                print(f"Failed to set up environment for {proj_name}-{bug_id}.")
                continue
            
            env_name = f'{proj_name}_{bug_id}_env'
            

            fixed_dir = os.path.join(single_bug_dir, 'fixed')
            buggy_dir = os.path.join(single_bug_dir, 'buggy')
            focal_dir = os.path.join(single_bug_dir, 'focal')
            
            # Create necessary directories
            os.makedirs(fixed_dir, exist_ok=True)
            os.makedirs(buggy_dir, exist_ok=True)
            os.makedirs(focal_dir, exist_ok=True)

            fixed_commit = bug_info['fixed_pr_id']
            buggy_commit = bug_info['buggy_id']
            
            try:
                env = os.environ.copy()
                env['PATH'] = f"{python_dir}:{env['PATH']}"
            
                if not os.path.exists(fixed_dir):
                    # Checkout fixed commit
                    subprocess.run(['git', 'checkout', fixed_commit], cwd=base_proj, check=True)
                    subprocess.run(['cp', '-r', '.', fixed_dir], cwd=base_proj, check=True)

                if not os.path.exists(buggy_dir):
                    # Checkout buggy commit
                    subprocess.run(['git', 'checkout', buggy_commit], cwd=base_proj, check=True)
                    subprocess.run(['cp', '-r', '.', buggy_dir], cwd=base_proj, check=True)
                
                if not os.path.exists(focal_dir):
                    subprocess.run(f'cp -r ./ * {focal_dir}', shell=True, cwd=fixed_dir, check=True)
                    
                    for buggy_file_name in bug_info["code_files"]:
                        buggy_file_path = os.path.join(buggy_dir, buggy_file_name)
                        to_be_replace_file_path = os.path.join(focal_dir, buggy_file_name)
                        
                        with open(buggy_file_path, 'r') as f:
                            buggy_content = f.read()
                        with open(to_be_replace_file_path, 'w') as f:
                            f.write(buggy_content)
                
                if 'pandas' in proj_name:
                    subprocess.run([f'git config --global --add safe.directory {fixed_dir}'], cwd=fixed_dir, env=env, check=True, shell=True)
                    subprocess.run([f'git config --global --add safe.directory {buggy_dir}'], cwd=buggy_dir, env=env, check=True, shell=True)
                    subprocess.run([f'git config --global --add safe.directory {focal_dir}'], cwd=focal_dir, env=env, check=True, shell=True)

                subprocess.run([f'conda run -n {env_name} {bugs_in_py_meta_data_dir}/{proj_name}/{proj_name}-{bug_id}/dependency_setup.sh'], cwd=fixed_dir, env=env, check=True, shell=True)
                
                with open(f'{log_dir}/{proj_name}-{bug_id}.log', 'a+') as f:
                    f.write(f"Set up fixed bug {bug_id} for project {proj_name} successfully.")
                
                # subprocess.run([f'conda run -n {env_name} {bugs_in_py_meta_data_dir}/{proj_name}/{proj_name}-{bug_id}/dependency_setup.sh'], cwd=buggy_dir, env=env, check=True, shell=True)
                
                subprocess.run([f'conda run -n {env_name} {bugs_in_py_meta_data_dir}/{proj_name}/{proj_name}-{bug_id}/dependency_setup.sh'], cwd=focal_dir, env=env, check=True, shell=True)
                
                with open(f'{log_dir}/{proj_name}-{bug_id}.log', 'a+') as f:
                    f.write(f"Set up focal bug {bug_id} for project {proj_name} successfully.")
                
                print(f"Set up bug {bug_id} for project {proj_name} successfully.")
                with open(f'{log_dir}/{proj_name}-{bug_id}.log', 'a+') as f:
                    f.write(f"Set up bug {bug_id} for project {proj_name} successfully.")
            except subprocess.CalledProcessError as e:
                with open(f'{log_dir}/{proj_name}-{bug_id}.log', 'w') as f:
                    f.write(f"Failed to set up bug {bug_id} for project {proj_name}: {e.output}")
                continue


def check_bugs_reproducible(info_file, bugs_in_py_meta_data_dir, bugs_in_py_checkout_proj_dir):
    with open(info_file, 'r') as f:
        all_bug_data = json.load(f)
        
    log_dir = f'{code_base}/data/logs/reproduce_test'
    os.makedirs(log_dir, exist_ok=True)
    
    for proj_name, bugs in all_bug_data.items():
        single_proj_dir = os.path.join(bugs_in_py_checkout_proj_dir, proj_name)
        
        for bug_id, bug_info in bugs.items():
            print(f'Checking bug {proj_name} {bug_id}')
            single_bug_dir = os.path.join(single_proj_dir, bug_id)
            
            env_name = f'{proj_name}_{bug_id}_env'
            
            focal_dir = os.path.join(single_bug_dir, 'focal')
            fixed_dir = os.path.join(single_bug_dir, 'fixed')
            
            if not os.path.join(focal_dir):
                print(f"Bug {bug_id} for project {proj_name} does not exist. Skipping.")
                continue
            
            test_cmds = []
            test_shell_file = os.path.join(bugs_in_py_meta_data_dir, proj_name, f'{proj_name}-{bug_id}', 'test.sh')
            with open(test_shell_file, 'r') as fr:
                for line in fr:
                    test_cmds.append(line.strip())
                
            if 'ansible' in proj_name:
                test_cmds = [f'PYTHONPATH=./lib {cmd}' for cmd in test_cmds]
            elif 'luigi' in proj_name:
                test_cmds = [f'PYTHONPATH=./ {cmd}' for cmd in test_cmds]
                
            test_cmd = '&&'.join(test_cmds)
            
            focal_test_cmd = subprocess.run(f'conda run -n {env_name} {test_cmd}', shell=True, cwd=focal_dir, capture_output=True, text=True)
            fixed_test_cmd = subprocess.run(f'conda run -n {env_name} {test_cmd}', shell=True, cwd=fixed_dir, capture_output=True, text=True)
            
            # pytest测试failed的话stderr有内容（包括fail这个词），returncode是1
            # pytest测试pass的话stderr是'',returncode是0
            
            # unittest测试failed的话stderr有内容（包括failed这个词）,returncode是1
            # unittest测试pass的话stderr有内容（不包括fail这个词）,returncode是0
            
            exe_res = ''
            if fixed_test_cmd.returncode == 0 and focal_test_cmd.returncode == 1:
                exe_res = 'Success reproduced!'
            else:
                exe_res = 'Failed to reproduce!'
            
            fixed_res = 'Pass' if fixed_test_cmd.returncode == 0 else 'Failed'
            focal_res = 'Pass' if focal_test_cmd.returncode == 0 else 'Failed'
            
            final_res = {
                'result': exe_res,
                'fixed': fixed_res,
                'focal': focal_res,
                'project': proj_name,
                'bug_id': bug_id,
                # 'fixed_output': fixed_test_cmd.stdout,
                'fixed_error': fixed_test_cmd.stderr,
                # 'focal_output': focal_test_cmd.stdout,
                'focal_error': focal_test_cmd.stderr
            }
                
            with open(f'{log_dir}/reproduce_records_new.log', 'a+') as f:
                f.write(json.dumps(final_res))
                f.write('\n')
                # f.json.dump(final_res, f)
                
            print(f"Reproduce result for bug {bug_id} of project {proj_name}: {exe_res}")

# clone_all_bugsinpy_repos(bugs_in_py_base_proj_dir, bugs_in_py_info_file)
# setup_envs(bugs_in_py_meta_data_dir, bugs_in_py_info_file)


# setup_bugsinpy_bugs(bugs_in_py_base_proj_dir, bugs_in_py_checkout_proj_dir, bugs_in_py_info_file, bugs_in_py_meta_data_dir)
check_bugs_reproducible(bugs_in_py_info_file, bugs_in_py_meta_data_dir, bugs_in_py_checkout_proj_dir)


# 首先setupenv的时候，建立conda环境，也许会出错，一般是需要修改 requirements.txt，里面会有一些冲突的包，或者是现在废弃的包，或者是linux不支持的包，进行对应的调整
# 然后setup dependency的时候，会出现一些问题，比如说setup.py文件中的一些问题，setuptools的版本（比如pandas）
# 最后执行测试，可能会出现在fixed版本上也失败，一般也是依赖包的版本问题（比如luigi的typing_extensions和typeguard版本）