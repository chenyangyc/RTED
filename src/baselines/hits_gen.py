import os
import re
import json
import pickle
import logging
import subprocess
from collections import defaultdict
from core.chatbot import ChatBot
from data.configurations import example_response, bugs_in_py_checkout_proj_dir, typebugs_checkout_proj_dir, code_base, conda_base, test_related_info_bugsinpy, test_related_info_typebugs, api_key, base_url, model, temperature
from utils.file_parse import extract_functions_for_llm, extract_imports_for_llm, change_assert_to_pass_in_test, refactor_test_res
from utils.run_test_util import write_test_file, run_test_and_collect_cov_lightweight, is_triggered


def reindent_model_output(model_output):
    pattern = r"```python(.*?)```"
    backup_pattern = r"```(.*?)```"
    # Find and extract the code snippet
    try:
        code_snippet = re.findall(pattern, model_output, re.DOTALL)[0]
    except:
        try:
            code_snippet = re.findall(backup_pattern, model_output, re.DOTALL)[0]
        except:
            code_snippet = model_output
    try:
        functions = extract_functions_for_llm(code_snippet)
    except:
        functions = []
        
    return code_snippet, functions 


def add_indent(origin_str, indent_num):
    new_str = []
    prefix_indent = '    ' * indent_num
    
    for i in origin_str.split('\n'):
        new_str.append(f'{prefix_indent}{i}')
    new_str = '\n'.join(new_str)
    return new_str


def construct_module_context(method):
    belong_module = method.belong_module
    
    all_imports = '\n'.join([i for i in belong_module.imports if 'import Queue' not in i])
    all_fields = '\n'.join(belong_module.fields)
    all_classes = [i.name for i in belong_module.classes]
    
    module_name = belong_module.name.replace('.py', '')

    return all_imports, all_fields, all_classes, module_name


def construct_class_context(method):
    belong_class = method.belong_class
    
    if belong_class:
        class_definition = f'class {belong_class.name}:'
        
        class_attrs = [add_indent(line, indent_num=1) for line in belong_class.attributes]
        class_attrs = '\n'.join(class_attrs)
        
        class_constructor = [add_indent(init_method, indent_num=1) for init_method in belong_class.init]
        class_constructor = '\n\n'.join(class_constructor)
        
        indented_method = add_indent(method.content, indent_num=1)
        class_context = f'# Focal class\n{class_definition}\n\n{class_attrs}\n\n{class_constructor}\n\n    # Focal method\n{indented_method}'
    else:
        class_context = '# Focal method' + '\n' + method.content
        
    return class_context


def construct_stage2_prompt(all_imports, all_fields, class_context, slicing_content, focal_method, used_framework, all_refined_imports_str, py_version):
    return f'''Here are the basic details about the method under test:
```python
{all_imports}\n\n{all_fields}\n\n{class_context}\n
```

- Slice:
```text
{str(slicing_content)}
```

Please generate a whole unit test file covering all blocks of the slice following the given steps:
1. Enumerate all used variables and methods within this block.
2. Analyze and enumerate all types of conditions this block is expected to handle.
3. For each condition within the block, devise test cases to encompass all corresponding lines.
For each condition group, infer the construction of input parameters and dependent objects and classes.

Please generate unit tests for the focal method `{focal_method.name}` using {used_framework} in Python {py_version}.
The import statements of the test file include \n```\n{all_refined_imports_str}\n```'
'''

def get_slice_json(slice_content: str) -> dict:
    pattern = r"</JSON format>```\s*(.*?)\s*```</JSON format>"
    match = re.search(pattern, slice_content, re.DOTALL)

    if not match:
        return slice_content

    json_str = match.group(1)

    try:
        data = json.loads(json_str)
        return json_str
    except json.JSONDecodeError as e:
        return slice_content

    return json_str

def run_single_method(origin_test_file, proj_name, bug_id, focal_method, focal_dir, fixed_dir, env_name, debugging_mode, prompt_cache_dict, tmp_dir_for_test, run_dataset, run_type):
    all_imports, all_fields, all_classes, module_name = construct_module_context(focal_method)
    
    module_path = focal_method.belong_module.module_path
    focal_module_dir = focal_dir + '/' if 'ansible' not in focal_dir else focal_dir + '/lib/'
    fixed_module_dir = fixed_dir + '/' if 'ansible' not in fixed_dir else fixed_dir + '/lib/'
    
    if run_type == 'buggy':
        module_relative_dir = module_path.replace(focal_module_dir, '').replace('.py', '').replace('/', '.')
    elif run_type == 'non_buggy':
        module_relative_dir = module_path.replace(fixed_module_dir, '').replace('.py', '').replace('/', '.')
    
    class_context = construct_class_context(focal_method)
    
    if run_dataset == 'typebugs':
        real_bug_id = bug_id.split('_')[0]
        used_framework = test_related_info[proj_name][real_bug_id]['used_framework']
        py_version = test_related_info[proj_name][real_bug_id]['py_version']
    else:
        used_framework = test_related_info[proj_name][bug_id]['used_framework']
        py_version = test_related_info[proj_name][bug_id]['py_version']
    
    system_prompt = f'''You are a senior tester in Python projects, your task is writing tests for a specific focal method in a focal class (A focal method and focal class means a method or class under test). If you provide code in your response, the code you write should be in format ```python <code> ```'''
        
    stage1_prompt = f'''Here are the basic details about the method under test:
```python
{all_imports}\n\n{all_fields}\n\n{class_context}\n
```

Please decompose the method `{focal_method.name}` under test following the instructions below:
1. Summarize the focal method.
2. List necessary environment settings to run the focal method:
    1) Invoked parameters and fields.
    2) Invoked methods.
3. Decompose the focal method into multiple problem-solving steps:
    1) Describe the subtask of the slice.
    2) Replicate the corresponding code statements.

Please output following the format in JSON, below is an example (JSON format), you can replace the content with your own code:
</JSON format>```
{{
    "Slice 1": {{
        "description": "",
        "code": ""
    }},
    "Slice 2": {{
        "description": "",
        "code": ""
    }}
}}
```</JSON format>
'''

    all_refined_imports = []
    all_refined_imports.append(f'import {module_relative_dir}')
    all_refined_imports.append(f'from {module_relative_dir} import *')

    all_refined_imports_str = '\n'.join(all_refined_imports)

    print('Querying the LLM...')
    logger.debug('Querying the LLM...')
    
    if not debugging_mode:
        chat_bot = ChatBot(api_key, base_url, model, system_prompt, temperature)
        
        if stage1_prompt in prompt_cache_dict.keys():
            stage1_response = prompt_cache_dict.get(stage1_prompt)
            logger.debug('Stage 1 prompt hit the cache!')
        else:
            stage1_response = chat_bot.chat(stage1_prompt, prefix_output='', add_to_history=False)
            prompt_cache_dict[stage1_prompt] = stage1_response
        
        slice_res = get_slice_json(stage1_response)
        stage2_prompt = construct_stage2_prompt(all_imports, all_fields, class_context, slice_res, focal_method, used_framework, all_refined_imports_str, py_version)
        
        if stage2_prompt in prompt_cache_dict.keys():
            stage2_response = prompt_cache_dict.get(stage2_prompt)
            logger.debug('Stage 2 prompt hit the cache!')
            chat_bot.add_history(stage2_prompt, stage2_response)
        else:
            stage2_response = chat_bot.chat(stage2_prompt, prefix_output='', add_to_history=True)
            prompt_cache_dict[stage2_prompt] = stage2_response
    else:
        stage1_prompt = ''
        stage1_response =  ''
        stage2_response = example_response
    
    print('Get the response!')
    logger.debug('Get the response!')
    
    with open(prompt_cache, 'wb') as f:
        pickle.dump(prompt_cache_dict, f)
    
    code_content, test_cases = reindent_model_output(stage2_response)
    code_content = change_assert_to_pass_in_test(code_content)
    
    try:
        processed_imports = extract_imports_for_llm(code_content)
    except:
        processed_imports = []
    
    for single_import in processed_imports:
        if module_name in single_import:
            code_content = code_content.replace(single_import, '')

    added_imports = [
        'import sys',
        'import unittest',
        'import os'
    ]
    all_refined_imports = all_refined_imports + added_imports
    
    new_imports = '\n'.join(all_refined_imports)
    code_content = new_imports + '\n' + code_content

    new_test_file = '/'.join(origin_test_file.split('/')[:-1]) + f'/test_{focal_method.name}_tttmp.py'
    
    focal_test_res, fixed_test_res, focal_stderr = execute_test(code_content, new_test_file, focal_method, used_framework, env_name, tmp_dir_for_test, focal_dir, fixed_dir)

    triggered, focal_type_error, fixed_type_error, focal_passed, fixed_passed = is_triggered(focal_test_res, fixed_test_res)
    logger.debug(f'focal type error: {focal_type_error}, focal passed: {focal_passed}')
    logger.debug(f'fixed type error: {fixed_type_error}, fixed passed: {fixed_passed}')
            
    if run_type == 'buggy':
        repair_condition = (not focal_type_error and not focal_passed)
    elif run_type == 'non_buggy':
        repair_condition = (not fixed_type_error and not fixed_passed)
        
    if repair_condition:
        repair_tries = 0
        while repair_tries < 3 and repair_condition:
            logger.debug(f'Bug id {proj_name}-{bug_id}: repair try {repair_tries + 1}')
            
            if run_type == 'buggy':
                refactored_focal_test_res = refactor_test_res(focal_test_res)
                error_msg = refactored_focal_test_res
            elif run_type == 'non_buggy':
                refactored_fixed_test_res = refactor_test_res(fixed_test_res)
                error_msg = refactored_fixed_test_res
            
            repair_prompt = f'The test file you provided is not working. It encounters unexpected errors. Please fix the test file and make it executable.\n\nThe error message is:\n```\n{error_msg}\n```\n\nPlease provide the complete fixed executable test file.'
            
            if repair_prompt in prompt_cache_dict.keys():
                repair_response = prompt_cache_dict.get(repair_prompt)
                logger.debug('Repair prompt hit the cache!')
                chat_bot.add_history(repair_prompt, repair_response)
            else:
                logger.debug('Repair prompt not in cache, querying the LLM...')
                logger.debug('Focal output: ' + error_msg)
                repair_response = chat_bot.chat(repair_prompt, prefix_output='', add_to_history=True)
                prompt_cache_dict[repair_prompt] = repair_response
                
            prompt_cache_dict[repair_prompt] = repair_response
            with open(prompt_cache, 'wb') as f:
                pickle.dump(prompt_cache_dict, f)
    
            code_content, test_cases = reindent_model_output(repair_response)
            code_content = change_assert_to_pass_in_test(code_content)
            
            new_test_file = '/'.join(origin_test_file.split('/')[:-1]) + f'/test_{focal_method.name}_tttmp.py'
    
            focal_test_res, fixed_test_res, focal_stderr = execute_test(code_content, new_test_file, focal_method, used_framework, env_name, tmp_dir_for_test, focal_dir, fixed_dir)

            triggered, focal_type_error, fixed_type_error, focal_passed, fixed_passed = is_triggered(focal_test_res, fixed_test_res)
            logger.debug(f'focal type error: {focal_type_error}, focal passed: {focal_passed}')
            logger.debug(f'fixed type error: {fixed_type_error}, fixed passed: {fixed_passed}')
            
            if run_type == 'buggy':
                repair_condition = (not focal_type_error and not focal_passed)
            elif run_type == 'non_buggy':
                repair_condition = (not fixed_type_error and not fixed_passed)
        
            repair_tries += 1

    return {
        'triggered': triggered,
        'focal_type_error': focal_type_error,
        'fixed_type_error': fixed_type_error,
        'focal_passed': focal_passed,
        'fixed_passed': fixed_passed,
        'focal_method': focal_method.content,
        'code_content': code_content,
        'focal_test_res': focal_test_res,
        'fixed_test_res': fixed_test_res,
        'module_path': module_path,
        'focal_module_dir': focal_module_dir,
        'module_relative_dir': module_relative_dir, 
        'stage1_prompt': stage1_prompt,
        'stage2_prompt': stage2_prompt,
        'stage1_response': stage1_response,
        'stage2_response': stage2_response,
        'processed_imports': processed_imports,
        'all_refined_imports': all_refined_imports
    }


def execute_test(test_content, relative_test_file, focal_method, used_framework, env_name, tmp_dir_for_test, focal_proj_dir, fixed_proj_dir):
    belong_module = focal_method.belong_module
    
    module_name = belong_module.name.replace('.py', '')
    module_path = belong_module.module_path
    
    focal_module_dir = focal_proj_dir
    fixed_module_dir = focal_module_dir.replace(focal_proj_dir, fixed_proj_dir)
    
    module_tmp_dir = os.path.join(tmp_dir_for_test, module_name)
    python_bin = f'{conda_base}/envs/{env_name}/bin/python'
    
    # subprocess.run([f'conda run -n {env_name} pip install unittest'], shell=True)
    
    # for index, test_case in enumerate([test_content]):
        # focal test
    
    test_case = test_content
    
    test_file, test_content = write_test_file(focal_module_dir, relative_test_file, test_case)

    focal_run_output, focal_stdout, focal_stderr = run_test_and_collect_cov_lightweight(focal_module_dir, test_file, relative_test_file, used_framework, module_tmp_dir, python_bin)
    
    # fixed test
    test_file, test_content = write_test_file(fixed_module_dir, relative_test_file, test_case)
    
    fixed_run_output, fixed_stdout, fixed_stderr = run_test_and_collect_cov_lightweight(fixed_module_dir, test_file, relative_test_file, used_framework, module_tmp_dir, python_bin)
    
    return focal_run_output, fixed_run_output, focal_stderr
    

def main(extracted_focal_method, debugging_mode, prompt_cache_dict, tmp_dir_for_test, json_res_file, run_dataset, run_type):

    with open(extracted_focal_method, 'rb') as f:
        all_focals = pickle.load(f)
        
    json_writer = open(
        json_res_file,
        "w",
        # encoding="utf-8",
    )
    for proj_name, proj_info in all_focals.items():
        print(f'Begin project {proj_name}')
        logger.debug(f'Begin project {proj_name}')
        
        for bug_id, bug_tests in proj_info.items():
            print(f'Begin bug id {proj_name}-{bug_id}')
            logger.debug(f'Begin bug id {proj_name}-{bug_id}')
            
            final_result = {
                'proj_name': proj_name,
                'bug_id': bug_id,
                'test_reses': []
            }
                
            for test_cmd, test_res in bug_tests.items():
                try:
                    chains = test_res['all_failed_methods']
                    
                    for single_chain in chains:
                        focal_method = None
                        for method in reversed(single_chain):
                            method_file = method[0]
                            method_obj = method[1]
                            
                            if 'env' not in method_file and 'test' not in method_file:
                                focal_method = method_obj
                        
                        if focal_method:
                            print(f'Bug id {proj_name}-{bug_id}: focal method extracted, begin testing')
                            logger.debug(f'Bug id {proj_name}-{bug_id}: focal method extracted, begin testing')
                            
                            index_cmd = test_cmd.replace('PYTHONPATH=./lib ', '').replace('PYTHONPATH=./ ', '')
                            
                            if run_dataset == 'bugs_in_py':
                                focal_dir = os.path.join(bugs_in_py_checkout_proj_dir, proj_name, bug_id, 'focal')
                                fixed_dir = os.path.join(bugs_in_py_checkout_proj_dir, proj_name, bug_id, 'fixed')
                                env_name = f'{proj_name}_{bug_id}_env'
                                origin_test_file = test_related_info[proj_name][bug_id]['test_files'][index_cmd]
                            
                                
                            elif run_dataset == 'typebugs':
                                focal_dir = os.path.join(typebugs_checkout_proj_dir, proj_name, bug_id, 'focal')
                                fixed_dir = os.path.join(typebugs_checkout_proj_dir, proj_name, bug_id, 'fixed')
                                real_bug_id = bug_id.split('_')[0]
                                env_name = f'{real_bug_id}_env'
                                origin_test_file = test_related_info[proj_name][real_bug_id]['test_files'][index_cmd]
                            
                            test_result = run_single_method(origin_test_file, proj_name, bug_id, focal_method, focal_dir, fixed_dir, env_name, debugging_mode, prompt_cache_dict, tmp_dir_for_test, run_dataset, run_type)
                            
                            final_result['test_reses'].append(test_result)
                            
                    print(f'Bug id {proj_name}-{bug_id}: testing completed')
                    logger.debug(f'Bug id {proj_name}-{bug_id}: testing completed')
                except Exception as e:
                    print(f'Bug id {proj_name}-{bug_id}: testing exception!!')
                    logger.debug(f'Bug id {proj_name}-{bug_id}: testing exception!!')
                    logger.error(f'Exception: {e}')
                    continue
                
            json_writer.write(json.dumps(final_result) + '\n')
            json_writer.flush()
            
            print(f'Finish bug id {proj_name}-{bug_id}')
            logger.debug(f'Finish bug id {proj_name}-{bug_id}')
        #     break
        # break

                        
if __name__ == '__main__':
    data_config = {
        'buggy': {
            'bugs_in_py': {
                'extracted_focal_method': 'data/extracted_focal_methods_bugsinpy_0412.pkl',
                'test_related_info': test_related_info_bugsinpy
            },
            # 'typebugs': {
            #     'extracted_focal_method': 'data/extracted_focal_methods_typebugs_0417.pkl',
            #     'test_related_info': test_related_info_typebugs
            # }
            'typebugs': {
                'extracted_focal_method': 'data/extracted_focal_methods_typebugs_0513.pkl',
                'test_related_info': test_related_info_typebugs
            }
            
        },
        'non_buggy': {
            'bugs_in_py': {
                'extracted_focal_method': 'data/extracted_focal_methods_bugsinpy_non_buggy_0501.pkl',
                'test_related_info': test_related_info_bugsinpy
            },
            # 'typebugs': {
            #     'extracted_focal_method': 'data/extracted_focal_methods_typebugs_non_buggy_0501.pkl',
            #     'test_related_info': test_related_info_typebugs
            # }
            'typebugs': {
                'extracted_focal_method': 'data/extracted_focal_methods_typebugs_non_buggy_0515.pkl',
                'test_related_info': test_related_info_typebugs
            }
        }
    }
    
    run_types = ['buggy', 'non_buggy']

    run_datasets = ['typebugs']
    
    for run_type in run_types:
        debugging_mode = False
            
        for run_dataset in run_datasets:
        
            date = f'hits_{run_dataset}_{run_type}'
            
            extracted_focal_method = os.path.join(code_base, data_config[run_type][run_dataset]['extracted_focal_method'])
            test_related_info_file = data_config[run_type][run_dataset]['test_related_info']
            
            with open(test_related_info_file, 'r') as f:
                test_related_info = json.load(f)

            prompt_cache_dir = os.path.join(code_base, 'data', 'prompt_cache')
            if not os.path.exists(prompt_cache_dir):
                os.makedirs(prompt_cache_dir)

            prompt_cache = os.path.join(prompt_cache_dir, f'{date}.pkl')
            
            if os.path.exists(prompt_cache):
                with open(prompt_cache, 'rb') as fr:
                    prompt_cache_dict = pickle.load(fr)
            else:
                prompt_cache_dict = defaultdict()

            
            log_file = os.path.join(code_base, 'data', 'logs', f'{date}.log')
            
            # Configure logger
            logger = logging.getLogger('current_file_logger')
            logger.setLevel(logging.DEBUG)  # 设置日志级别
            
            # 创建handler，用于输出到控制台
            # console_handler = logging.StreamHandler()
            console_handler = logging.FileHandler(log_file)
            console_handler.setLevel(logging.DEBUG)
            
            # 创建formatter，并添加到handler
            formatter = logging.Formatter('[%(asctime)s - %(filename)s - %(funcName)s] - %(message)s')
            console_handler.setFormatter(formatter)
            
            # 将handler添加到logger
            logger.addHandler(console_handler)

            tmp_dir_for_test = os.path.join(code_base, 'data', 'temp_dirs', f'tmp_{date}')
            os.makedirs(tmp_dir_for_test, exist_ok=True)

            json_res_file = os.path.join(code_base, 'data', 'res_info', f'{date}.jsonl')
            os.makedirs(os.path.join(code_base, 'data', 'res_info'), exist_ok=True)
            

            main(extracted_focal_method, debugging_mode, prompt_cache_dict, tmp_dir_for_test, json_res_file, run_dataset, run_type) 
            
            with open(prompt_cache, 'wb') as fw:
                pickle.dump(prompt_cache_dict, fw)