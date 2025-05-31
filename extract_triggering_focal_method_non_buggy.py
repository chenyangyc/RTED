import pickle
from utils.file_parse import extract_module


def analyze_call_chain(method_call_list):
    processed_call_list = []
    
    for single_chain in method_call_list:
        processed_chain = []
        
        for single_function_info in single_chain:
            single_function = single_function_info[1]
            function_path = single_function_info[0]
            
            if 'wrapper' in single_function.content:
                continue
            if 'anaconda' in function_path:
                break
            
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
            
            processed_chain.append((fixed_function_path, new_single_function))
        
        processed_call_list.append(processed_chain)    
    return processed_call_list


if __name__ == '__main__':
    data_path = {
        'typebugs': {
            'input': '/data/yangchen/llm_teut/data/extracted_focal_methods_typebugs_0513.pkl',
            'output': '/data/yangchen/llm_teut/data/extracted_focal_methods_typebugs_non_buggy_0515.pkl'
        },
        'bugsinpy': {
            'input': '/data/yangchen/llm_teut/data/extracted_focal_methods_bugsinpy_0501.pkl',
            'output': '/data/yangchen/llm_teut/data/extracted_focal_methods_bugsinpy_non_buggy_0501.pkl',
        },
    }
    # benchmark_names = ['typebugs', 'bugsinpy']
    benchmark_names = ['typebugs']
    # 'typebugs' or 'bugsinpy'
    for benchmark_name in benchmark_names:
        input_path = data_path[benchmark_name]['input']
        output_path = data_path[benchmark_name]['output']
        
        with open(input_path, 'rb') as f:
            data = pickle.load(f)
            
        chain_cnt = 0
        for proj, proj_value in data.items():
            for bug_id, bug_value in proj_value.items():
                for test_cmd, test_value in bug_value.items():

                    method_call_list = test_value['all_failed_methods']
                    processed_method_call_list = analyze_call_chain(method_call_list)
                    
                    test_value['all_failed_methods'] = processed_method_call_list

        with open(output_path, 'wb') as f:
            pickle.dump(data, f)