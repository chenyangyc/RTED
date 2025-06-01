from data.configurations import code_base, judgement_system_prompt, api_key, base_url, model, temperature, test_related_info_bugsinpy, test_related_info_typebugs
from core.chatbot import ChatBot
import json
import pickle
import os
from collections import defaultdict
import logging


def load_cache_results(result_jsonl_file):
    with open(result_jsonl_file, 'r') as fr:
        all_lines = fr.readlines()
    
    all_result_cache = defaultdict()
    for single_line in all_lines:
        single_line = json.loads(single_line)
        proj_name = single_line['proj_name']
        bug_id = single_line['bug_id']
        test_reses = single_line['test_reses']
        
        if proj_name not in all_result_cache.keys():
            all_result_cache[proj_name] = defaultdict()
        
        if bug_id not in all_result_cache[proj_name].keys():
            all_result_cache[proj_name][bug_id] = defaultdict()
        
        all_result_cache[proj_name][bug_id] = test_reses
    
    return all_result_cache


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


def run_single_judgement(called_name_chain, type_inference_history):
    inference_history_str = ''
    for i in type_inference_history:
        inference_history_str += 'Question: \n' + i['question'] + '\n'
        inference_history_str += 'Analysis: \n' + i['answer'] + '\n'
        inference_history_str += '\n'
        
    user_prompt = f'''The chain you are going to analyze is: {called_name_chain}.
You are given the following call chain and parameter flow analysis result: \n{inference_history_str}.

Based on the above information, determine whether this parameter flow is at risk of causing a TypeError when executed.
Please return your answer in the following format:
```json
{{
    "risk_level": "high" | "moderate" | "low",
    "justification": "Concise reasoning based on type mismatches, unsafe operations, or risky transformations along the chain."
}}

### Example Output
```json
{{
    "risk_level": "high",
    "justification": "The parameter is inferred as a string at funcB, but funcC applies list-specific operations like 'append'. This type mismatch is likely to cause a TypeError at runtime."
}}
'''
    chatbot = ChatBot(api_key, base_url, model, judgement_system_prompt, temperature)
    
    actual_prompt = chatbot.get_history() + f"Question: {user_prompt}\n"
    
    if actual_prompt in prompt_cache_dict.keys():
        logger.debug('Prompt hit the cache!')
        response = prompt_cache_dict.get(actual_prompt)
    else:
        logger.debug('Querying LLM...')
        response = chatbot.chat(user_prompt, prefix_output='', add_to_history=False)
        
    logger.info(f'Judgement response: {response}')
    prompt_cache_dict[actual_prompt] = response

    with open(prompt_cache, 'wb') as f:
        pickle.dump(prompt_cache_dict, f)

    return {
        "prompt": user_prompt,
        "response": response
    }
    pass


def main(extracted_focal_method, type_inference_result_dir, json_res_file, all_cached_res):
    with open(extracted_focal_method, 'rb') as f:
        all_focals = pickle.load(f)
        
    json_writer = open(
        json_res_file,
        "w",
    )
    for proj_name, proj_info in all_focals.items():
        print(f'Begin project {proj_name}')
        logger.debug(f'Begin project {proj_name}')
        
        for bug_id, bug_tests in proj_info.items():
            print(f'Begin bug id {proj_name}-{bug_id}')
            logger.debug(f'Begin bug id {proj_name}-{bug_id}')

            cached_res = all_cached_res[proj_name][bug_id]
            
            final_result = {
                'proj_name': proj_name,
                'bug_id': bug_id,
                'test_reses': []
            }
            
            for single_cache_res in cached_res:

                for test_cmd, test_res in bug_tests.items():
                    try:
                        chains = test_res['all_failed_methods']
                        
                        for chain_index, single_chain in enumerate(chains):
                            focal_method = None
                            for focal_index, method in enumerate(single_chain):
                                method_file = method[0]
                                method_obj = method[1]
                                
                                if 'env' not in method_file and 'test' not in method_file:
                                    focal_method = method_obj
                                    break
                            
                            for method in reversed(single_chain):
                                method_file = method[0]
                                method_obj = method[1]
                                
                                if 'env' not in method_file and 'test' not in method_file:
                                    break

                            called_name_chain = ' -> '.join([single_func[1].name for single_func in single_chain[focal_index:]])
                            
                            if focal_method:
                                print(f'Bug id {proj_name}-{bug_id}: focal method extracted, begin testing')
                                logger.debug(f'Bug id {proj_name}-{bug_id}: focal method extracted, begin testing')

                                type_inference_history = load_type_inference_history(proj_name, bug_id, chain_index + 1, type_inference_result_dir)
                                
                                test_result = run_single_judgement(called_name_chain, type_inference_history)

                                final_result['test_reses'].append(test_result)                    

                        print(f'Bug id {proj_name}-{bug_id}: single cmd testing completed')
                        logger.debug(f'Bug id {proj_name}-{bug_id}: single cmd testing completed')
                    except Exception as e:
                        print(f'Bug id {proj_name}-{bug_id}: testing exception!!')
                        logger.debug(f'Bug id {proj_name}-{bug_id}: testing exception!!')
                        logger.error(f'Error: {e}')
                        continue

            json_writer.write(json.dumps(final_result) + '\n')
            json_writer.flush()
            
            print(f'Finish bug id {proj_name}-{bug_id}')
            logger.debug(f'Finish bug id {proj_name}-{bug_id}')

                        
if __name__ == '__main__':
    
    run_datasets = ['bugs_in_py', 'typebugs']
    chain_types = ['iterative', 'seperate']
    
    for run_dataset in run_datasets:
        for chain_type in chain_types:
            date_prefix = '0513_risk_judgement'
            date = f"{date_prefix}_{chain_type}"

            # Define configs
            dataset_config = {
                'bugs_in_py': {
                    'extracted_focal_method': 'data/extracted_focal_methods_bugsinpy_0412.pkl',
                    'test_info_file': test_related_info_bugsinpy,
                    'type_inference_result_dir': {
                        'iterative': 'data/infered_results/0416_iterative_chain',
                        'seperate': 'data/infered_results/0414'
                        
                    },
                    'prompt_cache': {
                        'iterative': 'data/prompt_cache/bugs_in_py/0426_our_repair_iterative_chain_no_raise.pkl',
                        'seperate': 'data/prompt_cache/bugs_in_py/0426_our_repair_seperate_chain_no_raise.pkl'
                    },
                    'res_cache': {  
                        'iterative': 'data/res_info/bugs_in_py/0426_our_repair_iterative_chain_no_raise.jsonl',
                        'seperate': 'data/res_info/bugs_in_py/0426_our_repair_seperate_chain_no_raise.jsonl'
                    }
                },
                'typebugs': {
                    'extracted_focal_method': 'data/extracted_focal_methods_typebugs_0417.pkl',
                    'test_info_file': test_related_info_typebugs,
                    'type_inference_result_dir': {
                        'iterative': 'data/infered_results/0418_iterative_chain_typebugs',
                        'seperate': 'data/infered_results/0426_seperate_chain_typebugs'
                        
                    },
                    'prompt_cache': {
                        'iterative': 'data/prompt_cache/typebugs/0426_our_repair_iterative_chain_no_raise_typebugs.pkl',
                        'seperate': 'data/prompt_cache/typebugs/0426_our_repair_seperate_chain_no_raise_typebugs.pkl'
                    },
                    'res_cache': {
                        'iterative': 'data/res_info/typebugs/0426_our_repair_iterative_chain_no_raise_typebugs.jsonl',
                        'seperate': 'data/res_info/typebugs/0426_our_repair_seperate_chain_no_raise_typebugs.jsonl'
                    }
                }
            }
            
            # Validate inputs
            if run_dataset not in dataset_config:
                raise ValueError(f"Unsupported run_dataset: {run_dataset}")
            if chain_type not in dataset_config[run_dataset]['type_inference_result_dir']:
                raise ValueError(f"Unsupported chain_type: {chain_type}")

            # Extract configs
            config = dataset_config[run_dataset]
            extracted_focal_method = os.path.join(code_base, config['extracted_focal_method'])

            res_cache_file = os.path.join(code_base, config['res_cache'][chain_type])
            
            all_cached_res = load_cache_results(res_cache_file)
            
            # Paths for inferred results
            type_inference_result_dir = os.path.join(code_base, config['type_inference_result_dir'][chain_type])

            # Setup result output path
            res_info_dir = os.path.join(code_base, 'data', 'res_info', run_dataset)
            os.makedirs(res_info_dir, exist_ok=True)
            json_res_file = os.path.join(res_info_dir, f'{date}.jsonl')

            prompt_cache_dir = os.path.join(code_base, 'data', 'prompt_cache', run_dataset)
            if not os.path.exists(prompt_cache_dir):
                os.makedirs(prompt_cache_dir)

            prompt_cache = os.path.join(prompt_cache_dir, f'{date}.pkl')
            if os.path.exists(prompt_cache):
                with open(prompt_cache, 'rb') as fr:
                    prompt_cache_dict = pickle.load(fr)
            else:
                prompt_cache_dict = defaultdict()
            
            log_dir = os.path.join(code_base, 'data', 'logs', run_dataset + '_judge')
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, f'{date}.log')
            
            # Configure logger
            logger = logging.getLogger('current_file_logger')
            logger.setLevel(logging.DEBUG)  # 设置日志级别
            
            logger.handlers.clear() 
            # 创建handler，用于输出到控制台
            # console_handler = logging.StreamHandler()
            console_handler = logging.FileHandler(log_file)
            console_handler.setLevel(logging.DEBUG)
            
            # 创建formatter，并添加到handler
            formatter = logging.Formatter('[%(asctime)s - %(filename)s - %(funcName)s] - %(message)s')
            console_handler.setFormatter(formatter)
            
            # 将handler添加到logger
            logger.addHandler(console_handler)

            main(extracted_focal_method, type_inference_result_dir, json_res_file, all_cached_res) 
            
            with open(prompt_cache, 'wb') as fw:
                pickle.dump(prompt_cache_dict, fw)