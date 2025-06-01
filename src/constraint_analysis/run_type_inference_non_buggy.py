import os
import json
import pickle
import logging
from collections import defaultdict
from core.chatbot import ChatBot
from data.configurations import example_prompt_1, example_prompt_2, example_response_1, example_response_2, api_key, base_url, model, temperature, code_base, iterative_infer_system_prompt, infer_system_prompt, infer_instruction_prompt


def generate_seperate_prompt(function_info, backward=True):
    # 利用被调用函数的type结果
    if backward:
        belong_function_name_info = f'The function belongs to class `{function_info["belong_class_name"]}`.\n' if function_info['belong_class_name'] else ''
        belong_function_init_info = f'The constructor of the class is:\n```python\n{function_info["belong_class_init"]}\n```\n' if function_info['belong_class_init'] else ''

        if function_info.get('split_result', 'false') == 'success':
            argument_info = f'Arguments passed to this called function: `{function_info["called_arguments"]}`.\n'
        else:
            argument_info = f''
        
        backward_info = f'''You are provided with type information for the arguments of the called function. Use this as backward-flow type information to guide your inference in the caller.
Function being called: `{function_info['called_function_name']}`.

Arguments defined in this called function: `{function_info['called_function_parameter']}`.
{argument_info}{belong_function_name_info}{belong_function_init_info}

Known type information for this called function's parameters:
{function_info['known_type_info']}'''

    else:
        backward_info = ''
    
    user_prompt = f'''The function `{function_info['function_name']}` needs to be analyzed is as below:
```python
{function_info['function_content']}
```
{backward_info}
Please infer the type, fields, methods, and built-in characteristics of each parameter based on its usage within the function `{function_info['function_name']}`, and using any constraints from the callee if available. Provide the result in JSON format. Please only output the JSON result without any additional explanations or comments.'''

    return user_prompt


def generate_type_seperate_prompt(call_chain, inference_prompt_cache_dict, infered_results):

    for i in range(len(call_chain) - 1, 0, -1):
        backward = False if i == len(call_chain) - 1 else True
        
        chatbot = ChatBot(api_key, base_url, model, infer_system_prompt, temperature)
        chatbot.add_history(infer_instruction_prompt, 'Sure, please provide the actual function code snippet.')
        chatbot.add_history(example_prompt_1, example_response_1)
        chatbot.add_history(example_prompt_2, example_response_2)
        
        user_prompt = generate_seperate_prompt(call_chain[i], backward)
        
        # chatbot.show_history()
        chat_history = chatbot.get_history()
        actual_prompt = f'{chat_history}\n{user_prompt}'
        
        if actual_prompt in inference_prompt_cache_dict:
            logger.debug(f'Prompt already exists in cache, using cached response...')
            response = inference_prompt_cache_dict[actual_prompt]
        else:
            logger.debug(f'Calling LLM...')
            response = chatbot.chat(user_prompt, '', True)
            inference_prompt_cache_dict[actual_prompt] = response
            logger.debug(f'Get the response...')

        call_chain[i]['llm_output'] = response
        call_chain[i - 1]['known_type_info'] = response
        
        called_function_name = call_chain[i]['called_function_name'] if backward else ''
        called_function_parameter = call_chain[i]['called_function_parameter'] if backward else ''
        if call_chain[i].get('split_result', 'false') == 'success':
            called_arguments = call_chain[i]['called_arguments'] 
        else:
            called_arguments = ''
        infered_results.append({
            'function_name': call_chain[i]['function_name'],
            'function_content': call_chain[i]['function_content'],
            'function_parameter': call_chain[i]['function_parameter'],
            'called_function_name': called_function_name,
            'called_function_parameter': called_function_parameter,
            'called_arguments': called_arguments,
            'user_prompt': user_prompt,
            'llm_output': response
        })
    pass


def generate_iterative_prompt(function_info, called_name_chain, backward=True):
    # 利用被调用函数的type结果
    if backward:
        belong_function_name_info = f'The function belongs to class `{function_info["belong_class_name"]}`.\n' if function_info['belong_class_name'] else ''
        belong_function_init_info = f'The constructor of the class is:\n```python\n{function_info["belong_class_init"]}\n```\n' if function_info['belong_class_init'] else ''

        if function_info.get('split_result', 'false') == 'success':
            argument_info = f'Arguments passed to this called function: `{function_info["called_arguments"]}`.\n'
        else:
            argument_info = f''
        
        backward_info = f'''You are provided with type information for the arguments of the called function. Use this as backward-flow type information to guide your inference in the caller.
Function being called: `{function_info['called_function_name']}`.

Arguments defined in this called function: `{function_info['called_function_parameter']}`.
{argument_info}{belong_function_name_info}{belong_function_init_info}

Known type information for this called function's parameters:
{function_info['known_type_info']}'''

        user_prompt = f'''The function `{function_info['function_name']}` in the call chain is as below, it calls the `{function_info['called_function_name']}` function:
```python
{function_info['function_content']}
```
{backward_info}
Please infer the type, fields, methods, and built-in characteristics of each parameter based on its usage within the function `{function_info['function_name']}`, and using any constraints from the callee if available. Provide the result in JSON format. Please only output the JSON result without any additional explanations or comments. If the constraints can not be satisfied, return \"Unable to satisfy!\" and summarize as required in the system prompt.'''

    else:
        backward_info = ''

        user_prompt = f'''The function `{function_info['function_name']}` is the last function in a function call chain (`{called_name_chain}`). There may (or may not) be a `TypeError` in this function:
```python
{function_info['function_content']}
```
{backward_info}
Please infer the type, fields, methods, and built-in characteristics of each parameter based on its usage within the function `{function_info['function_name']}` to trigger the potential TypeError. Provide the result in JSON format. Please only output the JSON result without any additional explanations or comments.'''

    return user_prompt


def generate_type_iterative_prompt(call_chain, inference_prompt_cache_dict, infered_results):
    infer_rounds = 0
    infer_completed = False
    previous_summarized_failures = []
    
    called_name_chain = ' -> '.join([single_func['function_name'] for single_func in call_chain])

    while infer_rounds < 3 and not infer_completed:
        logger.debug(f'Round {infer_rounds} of type inference...')
        temp_infer_process = []
        chatbot = ChatBot(api_key, base_url, model, iterative_infer_system_prompt, temperature)
        chatbot.add_history(example_prompt_1, example_response_1)
        chatbot.add_history(example_prompt_2, example_response_2)
        
        summarized_failure = '\n'.join(previous_summarized_failures)
        if summarized_failure != '':
            chatbot.add_history(f'Here are some previous rounds of type inference that encounter unsatisfiable constraints, as summarized below: {summarized_failure}', 'OK. I will infer again and avoid the same failure.')
            
        for i in range(len(call_chain) - 1, 0, -1):
            backward = False if i == len(call_chain) - 1 else True
            
            user_prompt = generate_iterative_prompt(call_chain[i], called_name_chain, backward)
            
            # chatbot.show_history()
            chat_history = chatbot.get_history()
            actual_prompt = f'{chat_history}\n{user_prompt}'
            
            if actual_prompt in inference_prompt_cache_dict:
                logger.debug(f'Prompt already exists in cache, using cached response...')
                response = inference_prompt_cache_dict[actual_prompt]
                chatbot.add_history(user_prompt, response)
            else:
                logger.debug(f'Calling LLM...')
                response = chatbot.chat(user_prompt, '', True)
                inference_prompt_cache_dict[actual_prompt] = response
                logger.debug(f'Get the response.')

            if 'unable to satisfy' in response.lower():
                previous_summarized_failures.append('- ' + response)
                logger.debug(f'Round {infer_rounds} inference failed, unable to satisfy constraints. Summarized failure: {response}')
                infer_rounds += 1
                break

            call_chain[i]['llm_output'] = response
            call_chain[i - 1]['known_type_info'] = response
            
            called_function_name = call_chain[i]['called_function_name'] if backward else ''
            called_function_parameter = call_chain[i]['called_function_parameter'] if backward else ''
            if call_chain[i].get('split_result', 'false') == 'success':
                called_arguments = call_chain[i]['called_arguments'] 
            else:
                called_arguments = ''
                
            temp_infer_process.append({
                'function_name': call_chain[i]['function_name'],
                'function_content': call_chain[i]['function_content'],
                'function_parameter': call_chain[i]['function_parameter'],
                'called_function_name': called_function_name,
                'called_function_parameter': called_function_parameter,
                'called_arguments': called_arguments,
                'user_prompt': user_prompt,
                'llm_output': response
            })
        infered_results.extend(temp_infer_process)
        infer_completed = True
    pass


if __name__ == '__main__':
    # run_datasets = ['bugs_in_py', 'typebugs']
    run_datasets = ['typebugs']
    run_types = ['iterative', 'seprate']
    
    for run_dataset in run_datasets:
        for run_type in run_types:
            date = f'0515_infer_type_non_buggy_{run_type}_chain_{run_dataset}'

            if run_dataset == 'bugs_in_py':
                with open(f'{code_base}/data/call_chain_info_non_buggy.json', 'r') as f:
                    call_chain_info = json.load(f)
            elif run_dataset == 'typebugs':
                # with open(f'{code_base}/data/call_chain_info_typebugs_non_buggy.json', 'r') as f:
                    # call_chain_info = json.load(f)
                with open(f'{code_base}/data/call_chain_info_typebugs_non_buggy_0515.json', 'r') as f:
                    call_chain_info = json.load(f)
            
            
            save_dir = os.path.join(code_base, 'data', 'infered_results', date)
            os.makedirs(save_dir, exist_ok=True)
            
            prompt_cache_dir = os.path.join(code_base, 'data', 'prompt_cache')
            if not os.path.exists(prompt_cache_dir):
                os.makedirs(prompt_cache_dir)
                
            prompt_cache = os.path.join(prompt_cache_dir, f'{date}.pkl')
            
            if os.path.exists(prompt_cache):
                with open(prompt_cache, 'rb') as fr:
                    inference_prompt_cache_dict = pickle.load(fr)
            else:
                inference_prompt_cache_dict = defaultdict()

            log_file = os.path.join(code_base, 'data', 'logs', 'infer_types', f'{date}.log')
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
            

            processed_chains = set()
            for proj, proj_value in call_chain_info.items():
                logger.debug(f'Processing project: {proj}')
                for bug_id, bug_value in proj_value.items():
                    logger.debug(f'Processing bug ID: {bug_id}')
                    chain_index = 0
                    for test_cmd, all_call_chain in bug_value.items():
                        logger.debug(f'Processing test command: {test_cmd}')
                        for single_call_chain in all_call_chain:
                            try:
                                chain_identifier = '-'.join([i['function_content'] for i in single_call_chain])
                                if chain_identifier in processed_chains:
                                    continue
                                
                                logger.debug(f'Processing call chain length: {len(single_call_chain)}')
                                infered_results = []
                                
                                if run_type == 'iterative':
                                    generate_type_iterative_prompt(single_call_chain, inference_prompt_cache_dict, infered_results)
                                    processed_chains.add(chain_identifier)
                                elif run_type == 'seperate':
                                    generate_type_seperate_prompt(single_call_chain, inference_prompt_cache_dict, infered_results)
                                    processed_chains.add(chain_identifier)
                                    
                                chain_index += 1

                                with open(f'{save_dir}/{proj}_{bug_id}_chain_{chain_index}.jsonl', 'a') as f:
                                    for result in infered_results:
                                        f.write(json.dumps(result) + '\n')
                                
                                with open(prompt_cache, 'wb') as fw:
                                    pickle.dump(inference_prompt_cache_dict, fw)
                            except:
                                logger.error(f'Error processing this call chain')
                                continue
                            
                        logger.debug(f'Finished processing test command: {test_cmd}')
                    logger.debug(f'Finished processing bug ID: {bug_id}')
                logger.debug(f'Finished processing project: {proj}')
            logger.debug('All processing completed.')