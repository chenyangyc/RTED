import pickle
import re
from collections import defaultdict


def reformat_prompt(prompt):
    # Ran * test in *s, use regrex to match
    pattern_1 = r"Ran\s+(\d+)\s+test\s+in\s+([\d.]+)s"
    pattern_2 = r"Ran\s+(\d+)\s+tests\s+in\s+([\d.]+)s"
    
    prompt_lines = prompt.split('\n')
    prompt_lines = [i for i in prompt_lines if not i.startswith('================') and not re.search(pattern_1, i) and not re.search(pattern_2, i)]
    prompt = '\n'.join(prompt_lines)
    return prompt


todo_prompt_cache_files = [
    '/data/yangchen/llm_teut/data/prompt_cache/bugs_in_py/0426_our_repair_iterative_chain_no_raise.pkl',
    '/data/yangchen/llm_teut/data/prompt_cache/bugs_in_py/0426_our_repair_seperate_chain_no_raise.pkl',
    '/data/yangchen/llm_teut/data/prompt_cache/typebugs/0426_our_repair_iterative_chain_no_raise_typebugs.pkl',
    '/data/yangchen/llm_teut/data/prompt_cache/typebugs/0426_our_repair_seperate_chain_no_raise_typebugs.pkl'
]


for single_cache_file in todo_prompt_cache_files[:1]:
    with open(single_cache_file, 'rb') as f:
        prompt_cache = pickle.load(f)
    
    for i in list(prompt_cache.keys()):
        if 'The test file you provided is not working.' in i:
            if 'mock' in i.lower():
                print(i)
            
            print('=' * 20)
            
    # processed_cache = defaultdict(list)
    
    # print(f"Loaded {single_cache_file} with {len(prompt_cache)} entries.")
    
    # to_be_deleted = []
    # for index, (key, value) in enumerate(prompt_cache.items()):
    #     if 'The test file you provided is not working.' in key:
    #         new_key = reformat_prompt(key)
    #         processed_cache[new_key].append(value)
    #         # delete it from the original cache
    #         to_be_deleted.append(key)
    #         pass
    # pass

    # for i in to_be_deleted:
    #     del prompt_cache[i]
        
    # for key, value_list in processed_cache.items():
    #     prompt_cache[key] = value_list
            
    # with open(single_cache_file, 'wb') as f:
    #     pickle.dump(prompt_cache, f)
    # print(f"Processed {single_cache_file} with {len(prompt_cache)} entries.")
    