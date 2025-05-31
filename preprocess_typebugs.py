import os
import json
import shutil
import subprocess
from loguru import logger
from data.configurations import typebugs_base_proj_dir, typebugs_checkout_proj_dir, typebugs_info_file, typebugs_meta_data_dir, conda_base, code_base, typebugs_setup_info_dir


def clone_all_typebugs_repos(typebugs_base_proj_dir, info_file):
    """
    Clone all repositories from TypeBugs information file.

    :param typebugs_base_proj_dir: Base directory to store all repositories.
    :param info_file: JSON file containing project and repository information.
    """
    # Load project data from JSON file
    with open(info_file, 'r') as f:
        all_data = json.load(f)
    
    # Map project names to their Git URLs
    proj_gitdir_dict = {proj.split('/')[0]: all_data[proj]['git'] for proj in all_data}

    # Clone each repository
    for proj_name, git_url in proj_gitdir_dict.items():
        single_proj_dir = os.path.join(typebugs_base_proj_dir, proj_name)

        if not os.path.exists(single_proj_dir):
            try:
                subprocess.run(['git', 'clone', git_url, single_proj_dir], check=True)
                print(f"Cloned {proj_name} successfully.")
            except subprocess.CalledProcessError as e:
                print(f"Failed to clone {proj_name} from {git_url}: {e}")


def setup_all_envs(typebugs_meta_data_dir, info_file):
    log_dir = f'{code_base}/data/logs/failed_envs'
    os.makedirs(log_dir, exist_ok=True)
    
    # Load project data from JSON file
    with open(info_file, 'r') as f:
        all_bug_data = json.load(f)
    
    res0 = subprocess.run(['conda', 'info', '-e'], text=True, capture_output=True, check=True)
    existing_envs = [line.split()[0] for line in res0.stdout.split('\n') if '#' not in line and line != '']
    
    for proj, bug_info in all_bug_data.items():
        proj_name = proj.split('/')[0]
        bug_id = proj.split('/')[-1]
        py_version = bug_info['py_version']
        env_name = f'{bug_id}_env'
        
        if 'airflow' in proj_name or 'core' in proj_name:
            continue
        if env_name in existing_envs:
            print(f"Environment {env_name} already exists. Skipping.")
            continue
        
        try:
            res1 = subprocess.run(['conda', 'create', '-n', env_name, f'python={py_version}'], input='y\n', text=True, capture_output=True, check=True)
            output = res1.stdout + res1.stderr
            
            requirements_files = f'{typebugs_meta_data_dir}/{proj_name}/{bug_id}/requirements.txt'
            res2 = subprocess.run([f'{conda_base}/envs/{env_name}/bin/pip', 'install', '--upgrade-strategy=only-if-needed','-r', requirements_files], capture_output=True)
            output = output+ res2.stdout.decode('utf-8') + res2.stderr.decode('utf-8')
            
            final_res = res1.returncode == 0 and res2.returncode == 0
        except subprocess.CalledProcessError as e:
            # os.makedirs()
            with open(f'{log_dir}/{bug_id}.log', 'w') as f:
                f.write(str(e))
            
            output = str(e.output)
            final_res = False
        
        if final_res == False:
            subprocess.run(['conda', 'remove', '-n', env_name, '--all'], input='y\n', text=True)
            with open(f'{log_dir}/{bug_id}.log', 'w') as f:
                f.write(f"Failed to create environment for {proj_name} with Python version {py_version}.")
                f.write(f'cmd: {conda_base}/envs/{env_name}/bin/pip install --upgrade-strategy=only-if-needed -r {requirements_files}')
                f.write(output)
        else:
            print(f'Success build {proj_name} env.\n')


def setup_single_proj_env(py_version, proj_name, bug_id, bugs_in_py_meta_data_dir):
    log_dir = f'{code_base}/data/logs/failed_envs'
    os.makedirs(log_dir, exist_ok=True)
    
    env_name = f'{bug_id}_env'
    
    return True, f'{conda_base}/{env_name}/bin'
    
    res0 = subprocess.run(['conda', 'info', '-e'], text=True, capture_output=True, check=True)
    existing_envs = [line.split()[0] for line in res0.stdout.split('\n') if '#' not in line and line != '']
    
    if env_name in existing_envs:
        print(f"Environment {env_name} already exists. Skipping.")
        return True, f'{conda_base}/{env_name}/bin'
        # subprocess.run(['conda', 'remove', '-n', env_name, '--all'], input='y\n', text=True)

    try:
        res1 = subprocess.run(['conda', 'create', '-n', env_name, f'python={py_version}'], input='y\n', text=True, capture_output=True, check=True)
        output = res1.stdout + res1.stderr
        
        requirements_files = f'{bugs_in_py_meta_data_dir}/{proj_name}/{bug_id}/requirements.txt'
        res2 = subprocess.run([f'{conda_base}/envs/{env_name}/bin/pip', 'install', '-r', requirements_files], capture_output=True)
        output = output+ res2.stdout.decode('utf-8') + res2.stderr.decode('utf-8')
        
        final_res = res1.returncode == 0 and res2.returncode == 0
    except subprocess.CalledProcessError as e:
        with open(f'{log_dir}/{bug_id}.log', 'w') as f:
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


def setup_typebugs_bugs(typebugs_base_proj_dir, typebugs_checkout_proj_dir, info_file, typebugs_meta_data_dir):
    """
    Set up buggy and fixed versions of projects.

    :param typebugs_base_proj_dir: Directory containing cloned repositories.
    :param typebugs_checkout_proj_dir: Base directory to store bug-specific versions.
    :param all_bug_data: JSON data with bug information.
    """
    # Load project data from JSON file
    with open(info_file, 'r') as f:
        all_bug_data = json.load(f)
    
    failed_log_dir = f'{code_base}/data/logs/failed_setup'
    os.makedirs(failed_log_dir, exist_ok=True)
    
    success_log_dir = f'{code_base}/data/logs/success_setup'
    os.makedirs(success_log_dir, exist_ok=True)
    
    failed_setup_path = f'{typebugs_setup_info_dir}/failed_setup.txt'
    with open(failed_setup_path, 'r') as f:
        failed_envs = f.readlines()
    failed_envs = [env.strip() for env in failed_envs]
    
    successful_setup_path = f'{typebugs_setup_info_dir}/successful_setup.txt'
    with open(successful_setup_path, 'r') as f:
        successful_setup = f.readlines()
    successful_setup = [env.strip() for env in successful_setup]
    
    for proj, bug_info in all_bug_data.items():
        proj_name = proj.split('/')[0]
        bug_id = proj.split('/')[-1]
        
        if bug_id in failed_envs:
            continue
        
        if bug_id != 'kivy-6954':
            continue
        
        base_proj = os.path.join(typebugs_base_proj_dir, proj_name)
        if not os.path.exists(base_proj):
            print(f"Base project directory {base_proj} does not exist. Skipping {proj_name}.")
            continue
        
        single_proj_dir = os.path.join(typebugs_checkout_proj_dir, proj_name)
        os.makedirs(single_proj_dir, exist_ok=True)
        
        for bug_path in bug_info["buglines"].keys():
            single_id = bug_path.split('/')[-1].split('.py')[0]
            file_name = single_id.split('-')[0] + '.py'
            buggy_file_name = '/'.join(bug_path.split('/')[:-1]) + '/' + file_name
            
            single_id = f'_{single_id}'
            single_bug_dir = os.path.join(single_proj_dir, f'{bug_id}{single_id}')
            
            # if f'{bug_id}{single_id}' != 'pandas-39028-1_aggregation':
            #     continue
            
            if f'{bug_id}{single_id}' in successful_setup:
                print(f"Bug {bug_id}{single_id} for project {proj_name} already exists. Skipping.")
                continue
            
            py_version = bug_info['py_version']
            is_env_set, python_dir = setup_single_proj_env(py_version, proj_name, bug_id, typebugs_meta_data_dir)
            if not is_env_set:
                print(f"Failed to set up environment for {proj_name}-{bug_id}.")
                continue
            env_name = f'{bug_id}_env'
        
            fixed_dir = os.path.join(single_bug_dir, 'fixed')
            focal_dir = os.path.join(single_bug_dir, 'focal')
            fixed_commit = bug_info['fixed_pr_id']
            
            try:
                env = os.environ.copy()
                env['PATH'] = f"{python_dir}:{env['PATH']}"
                # env['http_proxy'] = 'http://172.18.31.12:7890'
                # env['https_proxy'] = 'http://172.18.31.12:7890'
                subprocess.run([f'git config --global --add safe.directory {base_proj}'], cwd=base_proj, env=env, check=True, shell=True)
                try:
                    if not os.path.exists(fixed_dir):
                        os.makedirs(fixed_dir, exist_ok=True)
                        # Checkout fixed commit
                        subprocess.run(['git', 'checkout', '-f', fixed_commit], cwd=base_proj, check=True)
                        subprocess.run(['cp', '-r', '.', fixed_dir], cwd=base_proj, check=True)
                        
                except subprocess.CalledProcessError as e:
                    with open(f'{failed_log_dir}/{bug_id}{single_id}.log', 'w') as f:
                        f.write(f"Failed to set up fixed version for {proj_name}-{bug_id}{single_id}: {e.output}")
                    shutil.rmtree(fixed_dir, ignore_errors=True)
                    continue
                try:
                    if not os.path.exists(focal_dir):
                        os.makedirs(focal_dir, exist_ok=True)
                        subprocess.run(f'cp -r ./ * {focal_dir}', shell=True, cwd=fixed_dir, check=True)
                    
                        buggy_file_path = os.path.join(typebugs_meta_data_dir, proj, bug_path)
                        to_be_replace_file_path = os.path.join(focal_dir, buggy_file_name)
                        
                        with open(buggy_file_path, 'r') as f:
                            buggy_content = f.read()
                        with open(to_be_replace_file_path, 'w') as f:
                            f.write(buggy_content)
                        
                except Exception as e:
                    with open(f'{failed_log_dir}/{bug_id}{single_id}.log', 'w') as f:
                        f.write(f"Failed to set up bug {bug_id}{single_id} for project {proj_name}")
                        f.write(f"Error: {e.stderr}")
                        f.write(f'Output: {e.stdout}')
                    shutil.rmtree(fixed_dir, ignore_errors=True)
                
                if proj_name == 'airflow':
                    try:
                        subprocess.run([f'conda run -n {env_name} pip install apache-airflow'], shell=True)
                    except subprocess.CalledProcessError as e:
                        with open(f'{failed_log_dir}/{bug_id}{single_id}.log', 'w') as f:
                            f.write(f"Failed to install apache-airflow for {proj_name}-{bug_id}{single_id}: {e}")
                            continue
                if proj_name == 'pandas':
                    try:
                        # subprocess.run([f'conda run -n {env_name} pip install Cython==0.29.37'], shell=True)
                        subprocess.run([f'conda run -n {env_name} pip install setuptools==58.2.0'], shell=True)
                    except subprocess.CalledProcessError as e:
                        with open(f'{failed_log_dir}/{bug_id}{single_id}.log', 'w') as f:
                            f.write(f"Failed to install Cython for {proj_name}-{bug_id}{single_id}: {e}")
                            continue
                if proj_name == 'scikit-learn':
                    try:
                        subprocess.run([f'conda run -n {env_name} pip install Cython==0.29.37'], shell=True)
                    except subprocess.CalledProcessError as e:
                        with open(f'{failed_log_dir}/{bug_id}{single_id}.log', 'w') as f:
                            f.write(f"Failed to install Cython for {proj_name}-{bug_id}{single_id}: {e}")
                            continue
                
                fix_result = subprocess.run([f'conda run -n {env_name} {typebugs_meta_data_dir}/{proj_name}/{bug_id}/dependency_setup.sh'], cwd=fixed_dir, env=env, check=True, shell=True, capture_output=True, text=True)
                focal_result = subprocess.run([f'conda run -n {env_name} {typebugs_meta_data_dir}/{proj_name}/{bug_id}/dependency_setup.sh'], cwd=focal_dir, env=env, check=True, shell=True, capture_output=True, text=True)
                
                if fix_result.returncode != 0 or focal_result.returncode != 0:
                    with open(f'{failed_log_dir}/{bug_id}{single_id}.log', 'w') as f:
                        f.write(f"Fixed version output: {fix_result.stdout}")
                        f.write(f"Focal version output: {focal_result.stdout}")
                        f.write(f"Fixed version error: {fix_result.stderr}")
                        f.write(f"Focal version error: {focal_result.stderr}")

                    with open(failed_setup_path, 'a+') as f:
                        f.write(f"{bug_id}{single_id}\n")
                    print(f"Failed to set up bug {bug_id}{single_id} for project {proj_name}.")
                
                else:
                    with open(f'{success_log_dir}/{bug_id}{single_id}.log', 'w') as f:
                        f.write(f"Set up bug {bug_id}{single_id} for project {proj_name} successfully.")
                        f.write(f"Fixed version output: {fix_result.stdout}")
                        f.write(f"Focal version output: {focal_result.stdout}")
                        f.write(f"Fixed version error: {fix_result.stderr}")
                        f.write(f"Focal version error: {focal_result.stderr}")
                        
                    # Write successful setup to file
                    with open(successful_setup_path, 'a+') as f:
                        f.write(f"{bug_id}{single_id}\n")
                    print(f"Set up bug {bug_id}{single_id} for project {proj_name} successfully.")
                
            except subprocess.CalledProcessError as e:
                with open(f'{failed_log_dir}/{bug_id}{single_id}.log', 'w') as f:
                    f.write(f"Failed to set up bug {bug_id}{single_id} for project {proj_name}")
                    f.write(f"Error: {e.stderr}")
                    f.write(f'Output: {e.stdout}')

                with open(failed_setup_path, 'a+') as f:
                    f.write(f"{bug_id}{single_id}\n")
                print(f"Failed to set up bug {bug_id}{single_id} for project {proj_name}.")
                continue


def check_passed(test_cmd, execution_res):
    returncode = execution_res.returncode
    stderr = execution_res.stderr
    
    if 'pytest' in test_cmd:
        return returncode == 0


def check_bugs_reproducible(info_file, typebugs_meta_data_dir, typebugs_checkout_proj_dir):
    with open(info_file, 'r') as f:
        all_bug_data = json.load(f)
        
    log_dir = f'{code_base}/data/logs/reproduce_test'
    os.makedirs(log_dir, exist_ok=True)
    
    # 成功setup的bug
    successful_setup_path = f'{typebugs_setup_info_dir}/successful_setup.txt'
    with open(successful_setup_path, 'r') as f:
        successful_setup = f.readlines()
    successful_setup = [env.strip() for env in successful_setup]
    
    # 成功reproduce的bug
    successful_reproduce_path = f'{typebugs_setup_info_dir}/successful_reproduce_check.txt'
    if not os.path.exists(successful_reproduce_path):
        with open(successful_reproduce_path, 'w') as f:
            f.write('')
    with open(successful_reproduce_path, 'r') as f:
        successful_reproduce = f.readlines()
    successful_reproduce = [env.strip() for env in successful_reproduce]
    
    # 记录失败的bug
    failed_reproduce_path = f'{typebugs_setup_info_dir}/failed_reproduce_check.txt'
    if not os.path.exists(failed_reproduce_path):
        with open(failed_reproduce_path, 'w') as f:
            f.write('')
    with open(failed_reproduce_path, 'r') as f:
        failed_reproduce = f.readlines()
    failed_reproduce = [env.strip() for env in failed_reproduce]
    
    for proj, bug_info in all_bug_data.items():
        proj_name = proj.split('/')[0]
        bug_id = proj.split('/')[-1]
        
        # if proj_name != 'numpy':
        #     continue
        if bug_id != 'salt-38947':
            continue
        
        single_proj_dir = os.path.join(typebugs_checkout_proj_dir, proj_name)
        
        for bug_path in bug_info["buglines"].keys():
            single_id = bug_path.split('/')[-1].split('.py')[0]
            single_id = f'_{single_id}'
            single_bug_dir = os.path.join(single_proj_dir, f'{bug_id}{single_id}')
            
            # if f'{bug_id}{single_id}' != 'scikit-learn-7064_base':
            #     continue
            
            if f'{bug_id}{single_id}' not in successful_setup:
                # print(f"Unfortunately, bug {bug_id}{single_id} for project {proj_name} does not setup. Skipping.")
                continue
            
            if f'{bug_id}{single_id}' in successful_reproduce:
                # print(f"Congratulation, bug {bug_id}{single_id} for project {proj_name} already exists. Skipping.")
                continue
            
            print(f'Checking bug {proj_name} {bug_id}{single_id}')
            
            env_name = f'{bug_id}_env'
            
            focal_dir = os.path.join(single_bug_dir, 'focal')
            fixed_dir = os.path.join(single_bug_dir, 'fixed')
            
            if not os.path.join(focal_dir):
                print(f"Bug {bug_id}{single_id} for project {proj_name} does not exist. Skipping.")
                continue
            
            test_cmds = []
            test_shell_file = os.path.join(typebugs_meta_data_dir, proj_name, f'{bug_id}', 'test.sh')
            with open(test_shell_file, 'r') as fr:
                for line in fr:
                    test_cmds.append(line.strip())
                
            if 'ansible' in proj_name:
                test_cmds = [f'PYTHONPATH=./lib {cmd}' for cmd in test_cmds]
            if 'luigi' in proj_name:
                test_cmds = [f'PYTHONPATH=./ {cmd}' for cmd in test_cmds]
            if 'sanic' in proj_name:
                test_cmds = [f'PYTHONPATH=./ {cmd}' for cmd in test_cmds]
            if 'scikit-learn' in proj_name:
                test_cmds = [f'PYTHONPATH=./ {cmd}' for cmd in test_cmds]
            # if 'numpy' in proj_name:
            #     test_cmds = [f'PYTHONPATH=./ {cmd}' for cmd in test_cmds]
            
            if 'luigi' in proj_name:
                update_cmds = ['pip install --upgrade typing_extensions']
                test_cmds = update_cmds + test_cmds
                # subprocess.run(f'conda run -n {env_name} {update_cmd}', shell=True, check=True)
            if 'rasa' in proj_name:
                update_cmds = ['pip install filelock']
                test_cmds = update_cmds + test_cmds
                # subprocess.run(f'conda run -n {env_name} {update_cmd}', shell=True, check=True)
            if 'rich' in proj_name:
                update_cmds = ['pip install --upgrade packaging', 'pip install --upgrade setuptools']
                test_cmds = update_cmds + test_cmds
                # subprocess.run(f'conda run -n {env_name} {update_cmd}', shell=True, check=True)
                # subprocess.run(f'conda run -n {env_name} pip install --upgrade setuptools', shell=True, check=True)
            if 'salt' in proj_name:
                update_cmds = ['pip install pytest-testinfra', 'pip uninstall testinfra']
                test_cmds = update_cmds + test_cmds
                # result = subprocess.run(f'conda run -n {env_name} {update_cmd}', shell=True, check=True, capture_output=True, text=True)
                # subprocess.run(f'conda run -n {env_name} pip uninstall testinfra', shell=True, check=True)
            if 'scikit-learn' in proj_name:
                update_cmds = ['pip install nose', 'pip install scipy==1.1.0']
                test_cmds = update_cmds + test_cmds
                # subprocess.run(f'conda run -n {env_name} pip install nose', shell=True, check=True)
                # subprocess.run(f'conda run -n {env_name} pip install scipy==1.1.0', shell=True, check=True)
            
            test_cmd = '&&'.join(test_cmds)
            test_cmd = f'source activate {env_name} && {test_cmd}'
            
            focal_test_cmd = subprocess.run(test_cmd, shell=True, executable="/bin/bash", cwd=focal_dir, capture_output=True, text=True)
            fixed_test_cmd = subprocess.run(test_cmd, shell=True, executable="/bin/bash", cwd=fixed_dir, capture_output=True, text=True)
            
            # pytest测试failed的话stderr有内容（包括fail这个词），returncode是1
            # pytest测试pass的话stderr是'',returncode是0
            
            # unittest测试failed的话stderr有内容（包括failed这个词）,returncode是1
            # unittest测试pass的话stderr有内容（不包括fail这个词）,returncode是0
            
            exe_res = ''
            if fixed_test_cmd.returncode == 0 and focal_test_cmd.returncode == 1:
                exe_res = 'Success reproduced!'
                with open(successful_reproduce_path, 'a+') as f:
                    f.write(f"{bug_id}{single_id}\n")
            else:
                exe_res = 'Failed to reproduce!'
                if f'{bug_id}{single_id}' not in failed_reproduce:
                    with open(failed_reproduce_path, 'a+') as f:
                        f.write(f"{bug_id}{single_id}\n")
            
            fixed_res = 'Pass' if fixed_test_cmd.returncode == 0 else 'Failed'
            focal_res = 'Pass' if focal_test_cmd.returncode == 0 else 'Failed'
            
            final_res = {
                'result': exe_res,
                'fixed': fixed_res,
                'focal': focal_res,
                'project': proj_name,
                'bug_id': bug_id,
                'single_id': single_id,
                'fixed_output': fixed_test_cmd.stdout,
                'fixed_error': fixed_test_cmd.stderr,
                'focal_output': focal_test_cmd.stdout,
                'focal_error': focal_test_cmd.stderr
            }
            with open(f'{log_dir}/typebugs_reproduce_records_new.log', 'a+') as f:
                f.write(json.dumps(final_res))
                f.write('\n')
                
            print(f"Reproduce result for bug {bug_id}{single_id} of project {proj_name}: {exe_res}")


def comment_out_line_in_file():
    """
    在指定文件夹中查找目标文件，并注释掉文件中指定的行。
    
    :param folder_path: 要搜索的文件夹路径
    :param target_file_name: 目标文件名
    :param target_line: 要注释掉的行内容
    """
    folder_path = '/data/yangchen/llm_teut/data/benchmarks/typebugs'  # 替换为你的文件夹路径
    target_file_name = 'dependency_setup.sh'
    target_line = 'pip install -r ./pyter_requirements.txt'
    # 遍历文件夹中的所有文件
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            # 检查文件名是否为目标文件名
            if file == target_file_name:
                file_path = os.path.join(root, file)
                # 读取文件内容
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # 修改文件内容
                with open(file_path, 'w', encoding='utf-8') as f:
                    for line in lines:
                        # 检查是否为目标行
                        if line.strip() == target_line:
                            # 注释掉该行
                            f.write(f"# {line}")
                        else:
                            f.write(line)


# # 处理typebugs 的pip install -r ./pyter_requirements.txt 问题
# comment_out_line_in_file()

# clone_all_typebugs_repos(typebugs_base_proj_dir, typebugs_info_file)
# setup_all_envs(typebugs_meta_data_dir, typebugs_info_file)
# setup_typebugs_bugs(typebugs_base_proj_dir, typebugs_checkout_proj_dir, typebugs_info_file, typebugs_meta_data_dir)

check_bugs_reproducible(typebugs_info_file, typebugs_meta_data_dir, typebugs_checkout_proj_dir)
# subprocess.run([f'conda activate pandas-33373_env'], shell=True, check=True)
# subprocess.run([f'conda info'], shell=True, check=True)