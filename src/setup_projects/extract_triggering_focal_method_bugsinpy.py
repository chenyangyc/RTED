import os
import re
import json
import pickle
import subprocess
from collections import defaultdict
# from core.chatbot import ChatBot
from utils.file_parse import extract_module
from data.configurations import bugs_in_py_info_file, bugs_in_py_meta_data_dir, bugs_in_py_checkout_proj_dir, code_base


def generate_cg_for_triggering_test(proj_dir, proj_name, bug_id, absolute_test_files):
    # python3 tool/Jarvis/jarvis_cli.py /data/yangchen/llm_teut/data/bugsinpy/checkout_projects/ansible/1/buggy/lib/ansible/galaxy/collection.py --package /data/yangchen/llm_teut/data/bugsinpy/checkout_projects/ansible/1/buggy -o example_ooo.json
    
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
    buggy_proj_dir = os.path.join(bugs_in_py_checkout_proj_dir, proj_name, bug_id, 'focal')
    
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
            print(f'Called functions for {func_sig}: {called_funcs}')
        all_called_funcs.extend(called_funcs)
    
    return all_called_funcs


def extract_method_chain_from_test_output(output, test_cmd, focal_dir):
    if 'pytest' in test_cmd:
        pattern = r".*?([\w./-]+):(\d+):.*"
        test_func_name = test_cmd.strip().split('::')[-1]
        # test_path = test_cmd.strip().split(' ')[-1].split('::')[0]
        # test_file_name = test_cmd.strip().split(' ')[-1].split('::')[0]
        split_format = f'{test_func_name}'
    elif 'unittest' in test_cmd:
        pattern = r'File "(.*)", line (\d+), in'
        test_func_name = test_cmd.strip().split('.')[-1]
        # test_path = test_cmd.strip().split(' ')[-1].split('.')[]
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


def extract_failed_methods(proj_name, bug_id, bug_info):

    env_name = f'{proj_name}_{bug_id}_env'
            
    focal_dir = os.path.join(bugs_in_py_checkout_proj_dir, proj_name, bug_id, 'focal')

    if not os.path.join(focal_dir):
        print(f"Bug {bug_id} for project {proj_name} does not exist. Skipping.")
        return None
    
    test_res = defaultdict()
    
    test_cmds = []
    test_shell_file = os.path.join(bugs_in_py_meta_data_dir, proj_name, f'{proj_name}-{bug_id}', 'test.sh')
    
    with open(test_shell_file, 'r') as fr:
        for line in fr:
            test_cmds.append(line.strip())
        
    if 'ansible' in proj_name:
        test_cmds = [f'PYTHONPATH=./lib {cmd}' for cmd in test_cmds]
    elif 'luigi' in proj_name:
        test_cmds = [f'PYTHONPATH=./ {cmd}' for cmd in test_cmds]
    
    # test_cmd = '&&'.join(test_cmds)
    for single_test in test_cmds:

        focal_test_cmd = subprocess.run(f'conda run -n {env_name} {single_test}', shell=True, cwd=focal_dir, capture_output=True, text=True)

        all_output = focal_test_cmd.stdout + focal_test_cmd.stderr
        all_chain_methods = extract_method_chain_from_test_output(all_output, single_test, focal_dir)

        test_res[single_test] = {
            'all_output': all_output,
            'all_chain_methods': all_chain_methods
        }
    
    return test_res


def extract_patched_methods(proj_name, bug_id, bug_info):
                
    code_files = bug_info['code_files']
    buggy_proj_dir = os.path.join(bugs_in_py_checkout_proj_dir, proj_name, bug_id, 'focal')
    
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

                # if int(line_no) in line2method and (file_path, line2method[int(line_no)]) not in single_final_methods:
                # if int(line_no) in line2method:
                #     single_final_methods.append((file_path, line2method[int(line_no)]))
                
                if int(line_no) in line2method:
                    if not single_final_methods:
                        single_final_methods.append((file_path, line2method[int(line_no)]))
                    elif (file_path, line2method[int(line_no)]) != single_final_methods[-1]:
                        single_final_methods.append((file_path, line2method[int(line_no)]))
    
            except:
                # print(f'Extract method from file and line error: {file_path}')
                continue
        if single_final_methods:
            final_methods.append(single_final_methods)
    return final_methods


def main():
    all_reses = defaultdict()
    with open(bugs_in_py_info_file, 'r') as f:
        all_bug_data = json.load(f)

    log_dir = f'{code_base}/data/logs/extract_focal'
    os.makedirs(log_dir, exist_ok=True)
            
    for proj_name, bugs in all_bug_data.items():
        # if 'fast' in proj_name:
        #     continue

        all_reses[proj_name] = defaultdict()
        
        for bug_id, bug_info in bugs.items():
            if any([i in f'{proj_name}_{bug_id}' for i in ['keras_22', 'luigi_25', 'pandas_111', 'pandas_158', 'spacy_5']]):
                continue
            
            # if f'{proj_name}_{bug_id}' != 'tornado_7':
            #     continue
            
            # if 'pandas_48' not in f'{proj_name}_{bug_id}':
            #     continue
            
            print(f'Processing {proj_name} {bug_id}')
            
            all_reses[proj_name][bug_id] = defaultdict()
            # triggering_called_methods = extract_triggering_test_called_methods(proj_name, bug_id, bug_info)
            
            # patched_file_and_line = extract_patched_methods(proj_name, bug_id, bug_info)
            # patched_methods = extract_method_from_file_and_line(patched_file_and_line)

            
            test_res = extract_failed_methods(proj_name, bug_id, bug_info)
            
            for single_test, test_info in test_res.items():
                all_chain_methods = test_info['all_chain_methods']
                all_output = test_info['all_output']

                if all_chain_methods:
                    all_failed_methods = extract_method_from_file_and_line(all_chain_methods)
                else:
                    all_failed_methods = []
                    print(f'{proj_name} {bug_id} {single_test} Empty !!')
                    continue
                
                all_reses[proj_name][bug_id][single_test] = {
                    # 'triggering_called_methods': triggering_called_methods,
                    # 'patched_methods': patched_methods,
                    'all_failed_methods': all_failed_methods,
                    'test_output': all_output
                    # 'candidate_focal_method': candidate_focal_method
                }
                pass
        
            print(f'{proj_name} {bug_id} Finish !!')
    
            with open(f'{code_base}/data/extracted_focal_methods_bugsinpy_0501.pkl', 'wb') as f:
                pickle.dump(all_reses, f)
            
# main()