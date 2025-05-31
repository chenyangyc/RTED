import os
import re
import json
import pickle
import logging
import subprocess
from collections import defaultdict
from core.chatbot import ChatBot
from data.configurations import example_response, bugs_in_py_checkout_proj_dir, code_base, conda_base, test_related_info_bugsinpy, api_key, base_url, model, temperature
from utils.file_parse import extract_functions_for_llm, extract_imports_for_llm, extract_module, change_assert_to_pass_in_test
from utils.run_test_util import write_test_file, run_test_and_collect_cov_lightweight, is_triggered



def reindent_model_output(model_output):
    pattern = r"```python(.*?)```"

    # Find and extract the code snippet
    code_snippet = re.findall(pattern, model_output, re.DOTALL)[0]

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

def construct_test_skeleton(origin_test_file_location, origin_test_func):
    single_test_module, all_test_classes, all_test_functions = extract_module(origin_test_file_location)
    
    filtered_funcs = []
    for single_func in all_test_functions:
        is_top_defined = True
        for other_func in all_test_functions:
            if single_func.name != other_func.name and all([i in other_func.line_range for i in single_func.line_range]):
                is_top_defined = False
                break
        if is_top_defined:
            filtered_funcs.append(single_func)
    
    all_test_functions = filtered_funcs
    
    all_imports = '\n'.join([i for i in single_test_module.imports if 'import Queue' not in i])
    all_fields = '\n'.join(single_test_module.fields)
    
    within_class_functions = [i for i in all_test_functions if i.func_type == 'within_class']
    standalone_functions = [i for i in all_test_functions if i.func_type == 'standalone']

    test_func = None
    for single_func in all_test_functions:
        if single_func.name == origin_test_func:
            test_func = single_func
            break

    standalone_should_keep_functions = []
    for single_func in standalone_functions:
        if 'test' not in single_func.name or single_func.content.startswith('@pytest.fixture()'):
            standalone_should_keep_functions.append(single_func)
    
    standalone_should_keep_function_content = '\n\n'.join([add_indent(i.content, indent_num=0) for i in standalone_should_keep_functions])
    module_context = f'{all_imports}\n\n{all_fields}\n\n{standalone_should_keep_function_content}'
    
    within_class_should_keep_functions = []
    test_class = test_func.belong_class
    
    truncated_test_method = test_func.content.split(f'def {test_func.name}')[0] + f'def {test_func.signature}:\n'
    
    if test_class:
        functions_within_test_class = [func for func in within_class_functions if func.belong_class.name == test_class.name]
        
        for single_func in functions_within_test_class:
            if 'test' not in single_func.name or single_func.content.startswith('@pytest.fixture()') or 'setup' in single_func.name.lower():
                within_class_should_keep_functions.append(single_func)
    
        class_definition = f'class {test_class.name}:'
            
        class_attrs = [add_indent(line, indent_num=1) for line in test_class.attributes]
        class_attrs = '\n'.join(class_attrs)
        if class_attrs != '':
            class_attrs = '\n\n' + class_attrs
        
        class_constructor = [add_indent(init_method, indent_num=1) for init_method in test_class.init]
        class_constructor = '\n\n'.join(class_constructor)
        if class_constructor != '':
            class_constructor = '\n\n' + class_constructor
        
        within_class_should_keep_function_content = '\n\n'.join([add_indent(i.content, indent_num=1) for i in within_class_should_keep_functions])
        if within_class_should_keep_function_content != '':
            within_class_should_keep_function_content = '\n\n' + within_class_should_keep_function_content
        
        indented_method = add_indent(truncated_test_method, indent_num=1)
    
        class_context = f'# Test class\n{class_definition}{class_attrs}{class_constructor}{within_class_should_keep_function_content}\n\n    # Test method\n{indented_method}'
    
    else:
        class_context = truncated_test_method

    test_skeleton = module_context + '\n\n' + class_context
    return test_skeleton
    

def run_single_method(origin_test_file, origin_test_func, proj_name, bug_id, focal_method, focal_dir, fixed_dir, env_name, debugging_mode, prompt_cache_dict, tmp_dir_for_test, type_inference_history):
    all_imports, all_fields, all_classes, module_name = construct_module_context(focal_method)
    
    module_path = focal_method.belong_module.module_path
    focal_module_dir = focal_dir + '/' if 'ansible' not in focal_dir else focal_dir + '/lib/'
    module_relative_dir = module_path.replace(focal_module_dir, '').replace('.py', '').replace('/', '.')
    
    class_context = construct_class_context(focal_method)
    
    used_framework = test_related_info[proj_name][bug_id]['used_framework']
    py_version = test_related_info[proj_name][bug_id]['py_version']
    
    origin_test_file_location = os.path.join(focal_dir, origin_test_file)
    test_skeleton = construct_test_skeleton(origin_test_file_location, origin_test_func)
    
    system_prompt = (
        "You are an intelligent and expert programming assistant that helps users write high-quality Python unit tests.\n"
        "You will first be provided with one or more rounds of type inference results. These describe the types, fields, methods, "
        "and built-in characteristics of parameters involved in a chain of function calls, inferred through their usage.\n"
        "After the type inference phase is complete, you will be provided with the focal function's code context.\n"
        "Your task is to generate meaningful and thorough Python unit tests for the focal function using the combined context "
        "from type inference and the function implementation.\n"
        "When generating code, always format it using triple backticks and the 'python' tag, like this: ```python <code> ```.\n"
        "Make sure the generated tests are syntactically correct, logically sound, and cover normal behavior, edge cases, "
        "and valid inputs based on the inferred types and structure."
    )
    
    stage1_prompt = f'The focal function is \"{focal_method.name}\", it is located in module {module_relative_dir}, and its context is as follows: \n```\n{all_imports}\n\n{all_fields}\n\n{class_context}\n```\n\nPlease infer the intension of the \"{focal_method.name}\"'
    
    # # all_refined_imports = all_imports.split('\n')
    # all_refined_imports = []
    # # all_refined_imports.append(f'from .{module_name} import *')
    # # all_refined_imports.append(f'from . import {module_name}')
    
    # # all_imports_from_focal = [f'from .{module_name} import {i}' for i in all_classes]
    # # all_refined_imports = all_refined_imports + all_imports_from_focal
    # all_refined_imports.append(f'import {module_relative_dir}')
    # all_refined_imports.append(f'from {module_relative_dir} import *')

    # all_refined_imports_str = '\n'.join(all_refined_imports)
    
    stage2_prompt = f'\nThe test file for the above mentioned method is:\n ```\n {test_skeleton}\n```\n\nThe test function to be completed is \'{origin_test_func}\'.\nThe focal method is \'{focal_method.name}\'.\n\nPlease complete the test function and provide the complete executable test file. Do not use `with pytest.raises(TypeError)` or `try-except` to catch the error. Instead, let the test fail naturally when a TypeError is raised. Do not omit any code in the provided test file.'
    
    # Please write one test case for the "{focal_method.name}" with the given method intension in {used_framework} using Python {py_version}.\nThe import statements of the test class include \n```\n{all_refined_imports_str}\n```'
    
    print('Querying the LLM...')
    logger.debug('Querying the LLM...')
    
    if not debugging_mode:
        chat_bot = ChatBot(api_key, base_url, model, system_prompt, temperature)
        
        if stage1_prompt in prompt_cache_dict.keys():
            logger.debug('Stage 1 hit the cache!')
            stage1_response = prompt_cache_dict.get(stage1_prompt)
            chat_bot.add_history(stage1_prompt, stage1_response)
        else:
            stage1_response = chat_bot.chat_with_additional_history(stage1_prompt, prefix_output='', add_to_history=True, additional_history=type_inference_history)
            prompt_cache_dict[stage1_prompt] = stage1_response
        
        new_prop = f"{stage1_prompt}\n{stage1_response}\n{stage2_prompt}"
        if new_prop in prompt_cache_dict.keys():
            logger.debug('Stage 2 hit the cache!')
            stage2_response = prompt_cache_dict.get(new_prop)
            chat_bot.add_history(stage2_prompt, stage2_response)
            code_content = '' 
            test_cases = []
        else:
            stage2_response = chat_bot.chat_with_additional_history(stage2_prompt, prefix_output='', add_to_history=True, additional_history=type_inference_history)
            prompt_cache_dict[new_prop] = stage2_response
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

    new_test_file = '/'.join(origin_test_file.split('/')[:-1]) + f'/test_{focal_method.name}_tttmp.py'
    
    focal_test_res, fixed_test_res, focal_stderr = execute_test(code_content, new_test_file, focal_method, used_framework, env_name, tmp_dir_for_test, focal_dir, fixed_dir)

    triggered, focal_type_error, fixed_type_error, focal_passed, fixed_passed = is_triggered(focal_test_res, fixed_test_res)
    logger.debug(f'focal type error: {focal_type_error}, focal passed: {focal_passed}')
    logger.debug(f'fixed type error: {fixed_type_error}, fixed passed: {fixed_passed}')
            
    
    if not focal_type_error and not focal_passed:
        repair_tries = 0
        while repair_tries < 3 and (not focal_type_error and not focal_passed):
            logger.debug(f'Bug id {proj_name}-{bug_id}: repair try {repair_tries + 1}')
            error_msg = focal_stderr if focal_stderr != '' else focal_test_res
            
            repair_prompt = f'The test file you provided is not working. It encounters unexpected errors. Please fix the test file and make it executable.\n\nThe error message is:\n```\n{error_msg}\n```\n\nPlease provide the complete fixed executable test file.'
            
            # if repair_prompt in prompt_cache_dict.keys():
            #     repair_response = prompt_cache_dict.get(repair_prompt)
            #     logger.debug('Repair prompt hit the cache!')
            #     chat_bot.add_history(repair_prompt, repair_response)
            # else:
            repair_response = chat_bot.chat_with_additional_history(repair_prompt, prefix_output='', add_to_history=True, additional_history=type_inference_history)
            
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
        'stage2_response': stage2_response
        # 'processed_imports': processed_imports,
        # 'all_refined_imports': all_refined_imports
    }


def execute_test(test_content, relative_test_file, focal_method, used_framework, env_name, tmp_dir_for_test, focal_proj_dir, fixed_proj_dir):
    belong_module = focal_method.belong_module
    
    module_name = belong_module.name.replace('.py', '')
    module_path = belong_module.module_path
    
    focal_module_dir = focal_proj_dir
    fixed_module_dir = focal_module_dir.replace(focal_proj_dir, fixed_proj_dir)
    
    module_tmp_dir = os.path.join(tmp_dir_for_test, module_name)
    python_bin = f'{conda_base}/envs/{env_name}/bin/python'
    
    test_case = test_content
    
    test_file, test_content = write_test_file(focal_module_dir, relative_test_file, test_case)

    focal_run_output, focal_stdout, focal_stderr = run_test_and_collect_cov_lightweight(focal_module_dir, test_file, relative_test_file, used_framework, module_tmp_dir, python_bin)
    
    # fixed test
    test_file, test_content = write_test_file(fixed_module_dir, relative_test_file, test_case)
    
    fixed_run_output, fixed_stdout, fixed_stderr = run_test_and_collect_cov_lightweight(fixed_module_dir, test_file, relative_test_file, used_framework, module_tmp_dir, python_bin)
    
    return focal_run_output, fixed_run_output, focal_stderr
    

def load_type_inference_history(proj_name, bug_id, chain_index, type_inference_result_dir):
    corresponding_chain_res = os.path.join(type_inference_result_dir, f'{proj_name}_{bug_id}_chain_{chain_index}.jsonl')
    if not os.path.exists(corresponding_chain_res):
        return []
    with open(corresponding_chain_res, 'r') as f:
        all_chain_res = f.readlines()
    all_chain_res = [json.loads(i) for i in all_chain_res]
    history = []
    for i in all_chain_res:
        history.append({"question":i['user_prompt'],"answer":i['llm_output']})
    return history


def main(extracted_focal_method, debugging_mode, prompt_cache_dict, type_inference_result_dir, tmp_dir_for_test, json_res_file):

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
        
        # if 'tornado' not in proj_name:
        #     continue
        
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
                    
                    for chain_index, single_chain in enumerate(chains):
                        focal_method = None
                        for method in single_chain:
                            method_file = method[0]
                            method_obj = method[1]
                            
                            if 'env' not in method_file and 'test' not in method_file:
                                focal_method = method_obj
                                break
                        
                        if focal_method:
                            print(f'Bug id {proj_name}-{bug_id}: focal method extracted, begin testing')
                            logger.debug(f'Bug id {proj_name}-{bug_id}: focal method extracted, begin testing')
                            
                            focal_dir = os.path.join(bugs_in_py_checkout_proj_dir, proj_name, bug_id, 'focal')
                            fixed_dir = os.path.join(bugs_in_py_checkout_proj_dir, proj_name, bug_id, 'fixed')
                            env_name = f'{proj_name}_{bug_id}_env'
                            
                            index_cmd = test_cmd.replace('PYTHONPATH=./lib ', '').replace('PYTHONPATH=./ ', '')
                            origin_test_file = test_related_info[proj_name][bug_id]['test_files'][index_cmd]
                            origin_test_func = test_related_info[proj_name][bug_id]['test_funcs'][index_cmd]
                            type_inference_history = load_type_inference_history(proj_name, bug_id, chain_index + 1, type_inference_result_dir)
                            
                            test_result = run_single_method(origin_test_file, origin_test_func, proj_name, bug_id, focal_method, focal_dir, fixed_dir, env_name, debugging_mode, prompt_cache_dict, tmp_dir_for_test, type_inference_history)
                            
                            final_result['test_reses'].append(test_result)
                        
                    print(f'Bug id {proj_name}-{bug_id}: testing completed')
                    logger.debug(f'Bug id {proj_name}-{bug_id}: testing completed')
                except Exception as e:
                    print(f'Bug id {proj_name}-{bug_id}: testing exception!!')
                    logger.debug(f'Bug id {proj_name}-{bug_id}: testing exception!!')
                    logger.error(e)
                    continue
                
            json_writer.write(json.dumps(final_result) + '\n')
            json_writer.flush()
            
            print(f'Finish bug id {proj_name}-{bug_id}')
            logger.debug(f'Finish bug id {proj_name}-{bug_id}')
        #     break
        # break

                        
if __name__ == '__main__':
    # date = '0425_our_repair_iterative_chain_no_raise'
    # debugging_mode = False 
    # type_inference_result_dir = os.path.join(code_base, 'data', 'infered_results', '0416_iterative_chain')

    date = '0426_our_repair_seperate_chain_no_raise'
    debugging_mode = False
    type_inference_result_dir = os.path.join(code_base, 'data', 'infered_results', '0414')
    
    
    extracted_focal_method = 'data/extracted_focal_methods_bugsinpy_0412.pkl'
    
    with open(test_related_info_bugsinpy, 'r') as f:
        test_related_info = json.load(f)

    prompt_cache_dir = os.path.join(code_base, 'data', 'prompt_cache')
    if not os.path.exists(prompt_cache_dir):
        os.makedirs(prompt_cache_dir)

    prompt_cache = os.path.join(prompt_cache_dir, f'0425_our_repair_seperate_chain_no_raise.pkl')
    
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
    
    main(extracted_focal_method, debugging_mode, prompt_cache_dict, type_inference_result_dir, tmp_dir_for_test, json_res_file) 
    
    with open(prompt_cache, 'wb') as fw:
        pickle.dump(prompt_cache_dict, fw)