import os
import re
import json
import pickle
import subprocess
from collections import defaultdict
# from core.chatbot import ChatBot
from utils.file_parse import extract_module
from data.configurations import typebugs_info_file, typebugs_meta_data_dir, typebugs_checkout_proj_dir, code_base, typebugs_setup_info_dir
from loguru import logger


def generate_cg_for_triggering_test(proj_dir, proj_name, bug_id, absolute_test_files):
    jarvis_dir = f'{code_base}/assistant_tools/Jarvis'
    jarvis_tool = 'tool/Jarvis/jarvis_cli.py'
    
    module_paths = ' '.join(absolute_test_files)
    
    output_file = f'{code_base}/data/triggering_test_cgs/{proj_name}_{bug_id}.json'
    
    generate_cmd = f'conda run -n llm python3 {jarvis_tool} {module_paths} --package {proj_dir} -o {output_file}'
    
    try:
        subprocess.run([generate_cmd], cwd=jarvis_dir, check=True, shell=True)
    except subprocess.CalledProcessError as e:
        raise e
    
    with open(output_file, 'r') as f:
        cg = json.load(f)
        
    return cg


def extract_triggering_test_called_methods(proj_name, bug_id, bug_info):
    buggy_proj_dir = os.path.join(typebugs_checkout_proj_dir, proj_name, bug_id, 'focal')
    
    test_files = bug_info['test_files']
    test_classes = bug_info['test_class']
    test_funcs = bug_info['test_func']
    
    absolute_test_files = [os.path.join(buggy_proj_dir, test_file) for test_file in test_files]
    
    cg = generate_cg_for_triggering_test(buggy_proj_dir, proj_name, bug_id, absolute_test_files)
    
    all_called_funcs = []
    for index, test_file in enumerate(test_files):
        test_class = '.' + test_classes[index] if test_classes else ''
        
        test_func = '.' + test_funcs[index]
        
        func_sig = test_file.replace('.py', '').replace('/', '.') + test_class + test_func
        
        called_funcs = cg.get(func_sig, [])
        
        called_funcs = [i for i in called_funcs if i.startswith(proj_name)]
        
        if called_funcs:
            logger.info(f'Called functions for {func_sig}: {called_funcs}')
        all_called_funcs.extend(called_funcs)
    
    return all_called_funcs


def extract_method_chain_from_test_output(output, test_cmd, focal_dir):
    if 'pytest' in test_cmd:
        pattern = r".*?([\w./-]+):(\d+):.*"
        test_func_name = test_cmd.strip().split('::')[-1]
        split_format = f'{test_func_name}'
    elif 'unittest' in test_cmd:
        pattern = r'File "(.*)", line (\d+), in'
        test_func_name = test_cmd.strip().split('.')[-1]
        split_format = f'ERROR: {test_func_name}'
        
    # split_format = test_func_name
    # if 'pytest' in test_cmd:
    #     split_format = '______________________________ test'
    # elif 'unittest' in test_cmd:
    #     split_format = '______________________________ test'

    # truncate till '------ Captured'
    if '------ Captured' in output:
        output = output.split('------ Captured')[0]
    
    if 'warnings summary' in output:
        output = output.split('warnings summary')[0]
        
    # matches = re.findall(pattern, output)
    
    splited_test_ouput = output.split(split_format)
    
    all_methods = []
    for single_output in splited_test_ouput:
        matches = re.findall(pattern, single_output)
        single_methods = []
        
        flag = False
        for single_match in matches:
            file_path = single_match[0]
            line_no = single_match[1]
            
            if '.py' not in file_path:
                continue
            
            if 'pytest' in test_cmd:
                file_path = os.path.join(focal_dir, file_path)
            
            if flag == False and 'test' not in file_path:
                continue
            else:
                flag = True
                
            # if (file_path, line_no) not in single_methods:
            if not single_methods:
                single_methods.append((file_path, line_no))
            elif (file_path, line_no) != single_methods[-1]:
                single_methods.append((file_path, line_no))
    
        if single_methods and single_methods not in all_methods:
            all_methods.append(single_methods)

    return all_methods


def extract_failed_methods(proj_name, bug_id, single_bug_dir):
    env_name = f'{bug_id}_env'
    focal_dir = os.path.join(single_bug_dir, 'focal')
    
    if not os.path.join(focal_dir):
        logger.error(f"Bug {bug_id} for project {proj_name} does not exist. Skipping.")
        return None
    
    test_res = defaultdict()
    test_cmds = []
    test_shell_file = os.path.join(typebugs_meta_data_dir, proj_name, f'{bug_id}', 'test.sh')
    
    with open(test_shell_file, 'r') as fr:
        for line in fr:
            test_cmds.append(line.strip())
    
    # add test cmd
    if 'ansible' in proj_name:
        test_cmds = [f'PYTHONPATH=./lib {cmd}' for cmd in test_cmds]
    if 'luigi' in proj_name:
        test_cmds = [f'PYTHONPATH=./ {cmd}' for cmd in test_cmds]
    if 'sanic' in proj_name:
        test_cmds = [f'PYTHONPATH=./ {cmd}' for cmd in test_cmds]
    if 'scikit-learn' in proj_name:
        test_cmds = [f'PYTHONPATH=./ {cmd}' for cmd in test_cmds]
    if 'numpy' in proj_name:
        test_cmds = [f'PYTHONPATH=./ {cmd}' for cmd in test_cmds]
    
    for single_test in test_cmds:
        test_cmd = f'source activate {env_name} && {single_test}'
        
        focal_test_cmd = subprocess.run(test_cmd, shell=True, executable="/bin/bash", cwd=focal_dir, capture_output=True, text=True)
        
        all_output = focal_test_cmd.stdout + focal_test_cmd.stderr
        all_chain_methods = extract_method_chain_from_test_output(all_output, single_test, focal_dir)
        
        test_res[single_test] = {
            'all_output': all_output,
            'all_chain_methods': all_chain_methods
        }
    
    return test_res


def extract_patched_methods(proj_name, bug_id, bug_info):
    code_files = bug_info['code_files']
    buggy_proj_dir = os.path.join(typebugs_checkout_proj_dir, proj_name, bug_id, 'focal')
    
    buggy_methods = set()
    for code_file in code_files:
        absolute_code_file = os.path.join(buggy_proj_dir, code_file)
        
        buggy_lines = bug_info['buglines'][code_file]

        for line in buggy_lines:
            buggy_methods.add((absolute_code_file, line))
    return list(buggy_methods)


def extract_method_from_file_and_line(file_and_lines):
    final_methods = []
    for single_chain in file_and_lines:
        single_final_methods = []
        for file_and_line in single_chain:
            file_path = file_and_line[0]
            line_no = file_and_line[1]
            try:
                single_module, all_classes, all_methods = extract_module(file_path)

                line2method = defaultdict()
                for single_method in all_methods:
                    for line in single_method.line_range:
                        line2method[line] = single_method
                
                if int(line_no) in line2method:
                    if not single_final_methods:
                        single_final_methods.append((file_path, line2method[int(line_no)]))
                    elif (file_path, line2method[int(line_no)]) != single_final_methods[-1]:
                        single_final_methods.append((file_path, line2method[int(line_no)]))
    
            except:
                logger.error(f'Extract method from file and line error: {file_path}')
                continue
        if single_final_methods:
            final_methods.append(single_final_methods)
    return final_methods


def main():
    all_reses = defaultdict()
    with open(typebugs_info_file, 'r') as f:
        all_bug_data = json.load(f)

    log_dir = f'{code_base}/data/logs/extract_focal_typebugs'
    os.makedirs(log_dir, exist_ok=True)
    
    # 成功reproduce的bug
    successful_reproduce_path = f'{typebugs_setup_info_dir}/successful_reproduce.txt'
    with open(successful_reproduce_path, 'r') as f:
        successful_reproduce = f.readlines()
    successful_reproduce = [env.strip() for env in successful_reproduce]
    
    for proj, bug_info in all_bug_data.items():
        proj_name = proj.split('/')[0]
        bug_id = proj.split('/')[-1]
        if proj_name not in all_reses:
            all_reses[proj_name] = defaultdict()
        # if bug_id not in all_reses[proj_name]:
        #     all_reses[proj_name][bug_id] = defaultdict()
        
        single_proj_dir = os.path.join(typebugs_checkout_proj_dir, proj_name)
        
        for bug_path in bug_info["buglines"].keys():
            single_id = bug_path.split('/')[-1].split('.py')[0]
            single_id = f'_{single_id}'
            single_bug_dir = os.path.join(single_proj_dir, f'{bug_id}{single_id}')
            
            if f'{bug_id}{single_id}' not in successful_reproduce:
                continue
            all_reses[proj_name][f'{bug_id}{single_id}'] = defaultdict()
            logger.info(f'{bug_id}{single_id} Start !!')
            
            test_res = extract_failed_methods(proj_name, bug_id, single_bug_dir)
            for single_test, test_info in test_res.items():
                all_chain_methods = test_info['all_chain_methods']
                all_output = test_info['all_output']

                if all_chain_methods:
                    all_failed_methods = extract_method_from_file_and_line(all_chain_methods)
                    logger.success(f'{bug_id}{single_id} {single_test} successfully extract methods')
                else:
                    all_failed_methods = []
                    logger.error(f'{bug_id}{single_id} {single_test} Empty !!')
                    continue
                
                all_reses[proj_name][f'{bug_id}{single_id}'][single_test] = {
                    # 'triggering_called_methods': triggering_called_methods,
                    # 'patched_methods': patched_methods,
                    'all_failed_methods': all_failed_methods,
                    'test_output': all_output
                    # 'candidate_focal_method': candidate_focal_method
                }
                pass
        
            logger.info(f'{bug_id}{single_id} Finish !!')

    with open(f'{code_base}/data/extracted_focal_methods_typebugs_0513.pkl', 'wb') as f:
        pickle.dump(all_reses, f)

main()