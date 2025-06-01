import pickle
from tree_sitter import Language, Parser
import tree_sitter_python as ts_python
import json
from loguru import logger
from utils.file_parse import extract_module


PYTHON_LANGUAGE = Language(ts_python.language())
parser = Parser()
parser.language = PYTHON_LANGUAGE

CALL_QUERY = PYTHON_LANGUAGE.query('(call)@call')
PARAMETERS_QUERY = PYTHON_LANGUAGE.query('(function_definition(parameters)@parameters)')


def get_function_parameter(function_content):
    root_node = parser.parse(bytes(function_content, 'utf8')).root_node
    function_parameter_nodes = PARAMETERS_QUERY.captures(root_node)
    
    if len(function_parameter_nodes.get('parameters', [])) == 0:
        raise ValueError("No function parameters found in the provided content.")
    
    parameter_content = function_parameter_nodes.get('parameters')[0].text.decode()
    return parameter_content


def splite_call_function(caller_function_content, called_function_name):
    root_node = parser.parse(bytes(caller_function_content, 'utf8')).root_node
    function_call_nodes = CALL_QUERY.captures(root_node)
    
    called_function_node = None
    for call_node in function_call_nodes.get('call', []):
        function = call_node.child_by_field_name('function')
        if function.type == 'identifier':
            function_name = function.text.decode()
            # function_obj = None
        elif function.type == 'attribute':
            # function_obj = function.child_by_field_name('object').text.decode()
            function_name = function.child_by_field_name('attribute').text.decode()
        else:
            continue
        if function_name == called_function_name:
            called_function_node = call_node
            break
    if called_function_node:
        end_byte = called_function_node.end_byte
        split_function = caller_function_content.encode()[:end_byte].decode() + '\n'
        arguments = called_function_node.child_by_field_name('arguments').text.decode()
        return {
            'result': 'success',
            'split_function': split_function,
            'called_arguments': arguments,
        }
    logger.error(f"Cannot find the called function {called_function_name} in the caller function content.")
    return {
        'result': 'failure',
        'split_function': caller_function_content,
        'called_arguments': '()',
    }

def analyze_call_chain(method_call_list):
    current_call_list = []
    split_call_chains = []
    
    for single_chain in method_call_list:
        current_call_list = []
        # now_call_list = []
        for single_function_info in single_chain:
            single_function = single_function_info[1]
            function_path = single_function_info[0]
            
            if 'wrapper' in single_function.content:
                continue
            if 'anaconda' in function_path:
                break
            if 'test' in single_function.name:
                if current_call_list and 'test' in current_call_list[0]['function_name']:
                    split_call_chains.append(current_call_list)
                current_call_list = []
            
            fixed_function_path = function_path.replace('focal', 'fixed')
            
            new_single_function = single_function
            
            try:
                single_module, all_classes, all_methods = extract_module(fixed_function_path)
                
                for single_fixed_method in all_methods:
                    if single_fixed_method.name == single_function.name :
                        if single_function.belong_class and single_fixed_method.belong_class and single_function.belong_class.name == single_fixed_method.belong_class.name:
                            new_single_function = single_fixed_method
                            break
                        elif not single_function.belong_class and not single_fixed_method.belong_class:
                            new_single_function = single_fixed_method
                            break
            except:
                print(f'Origin function / Fixed function not match!')
            
            current_call_list.append({
                'function_name': new_single_function.name,
                'function_content': new_single_function.content,
                'function_parameter': get_function_parameter(new_single_function.content),
                'belong_class_content': new_single_function.belong_class.content if new_single_function.belong_class else None,
                'belong_class_name': new_single_function.belong_class.name if new_single_function.belong_class else None,
                'belong_class_init': '\n'.join(new_single_function.belong_class.init) if new_single_function.belong_class else None,
            })
        if current_call_list and 'test' in current_call_list[0]['function_name']:
        # if current_call_list:
            split_call_chains.append(current_call_list)
    return split_call_chains


if __name__ == '__main__':
    data_path = {
        # 'typebugs': {
        #     'input': 'data/extracted_focal_methods_typebugs_0417.pkl',
        #     'output': 'data/call_chain_info_typebugs_non_buggy.json'
        # },
        'typebugs': {
            'input': 'data/extracted_focal_methods_typebugs_non_buggy_0515.pkl',
            'output': 'data/call_chain_info_typebugs_non_buggy_0515.json'
        },
        'bugsinpy': {
            'input': 'data/extracted_focal_methods_bugsinpy_0501.pkl',
            'output': 'data/call_chain_info_non_buggy.json',
        },
    }
    benchmark_name = 'typebugs'  # 'typebugs' or 'bugsinpy'
    
    input_path = data_path[benchmark_name]['input']
    output_path = data_path[benchmark_name]['output']
    with open(input_path, 'rb') as f:
        data = pickle.load(f)

    call_chain_info = {}

    chain_cnt = 0
    for proj, proj_value in data.items():
        call_chain_info[proj] = {}
        for bug_id, bug_value in proj_value.items():
            call_chain_info[proj][bug_id] = {}
            for test_cmd, test_value in bug_value.items():
                # logger.info(f"Processing {bug_id} {test_cmd}")
                call_chain_info[proj][bug_id][test_cmd] = []
                method_call_list = test_value['all_failed_methods']
                split_call_chains = analyze_call_chain(method_call_list)
                call_chain_info[proj][bug_id][test_cmd] = split_call_chains
                logger.info(f"{bug_id} {test_cmd} {len(split_call_chains)}")
                # chain_cnt += len(split_call_chains)
                for call_chain in split_call_chains:
                    for i in range(len(call_chain) - 1, 1, -1):
                        called_function_name = call_chain[i]['function_name']
                        caller_function_content = call_chain[i - 1]['function_content']
                        split_result = splite_call_function(caller_function_content, called_function_name)
                        call_chain[i - 1]['called_function_name'] = called_function_name
                        call_chain[i - 1]['called_function_content'] = split_result['split_function']
                        call_chain[i - 1]['called_arguments'] = split_result['called_arguments']
                        call_chain[i - 1]['called_function_parameter'] = call_chain[i]['function_parameter']
                        call_chain[i - 1]['split_result'] = split_result['result']
                # logger.info(f"Finished processing {bug_id} {test_cmd}")
    print(f"Total call chains: {chain_cnt}")
    with open(output_path, 'w') as f:
        json.dump(call_chain_info, f, indent=4)