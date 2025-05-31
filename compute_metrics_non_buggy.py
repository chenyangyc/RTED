import json
import os
from collections import defaultdict
from data.configurations import code_base


base_res_dir = f'{code_base}/data/res_info'
# Define configs
dataset_config = {
    'bugs_in_py': {
        'chat_tester': os.path.join(base_res_dir, '0501_chattester_bugs_in_py_non_buggy.jsonl'),
        'symprompt': os.path.join(base_res_dir, '0501_symprompt_bugs_in_py_non_buggy.jsonl'),
        'hits': os.path.join(base_res_dir, '0501_hits_bugs_in_py_non_buggy.jsonl'),
        'our_iterative_no_rethink': os.path.join(base_res_dir, 'bugs_in_py','0502_our_no_rethink_iterative_non_buggy.jsonl'),
        'our_seperate_no_rethink': os.path.join(base_res_dir, 'bugs_in_py','0502_our_no_rethink_seperate_non_buggy.jsonl'),
        'our_iterative': os.path.join(base_res_dir, 'bugs_in_py','0502_our_iterative_non_buggy.jsonl'),
        'our_seperate': os.path.join(base_res_dir, 'bugs_in_py','0502_our_seperate_non_buggy.jsonl')
    },
    'typebugs': {
        'chat_tester': os.path.join(base_res_dir, '0501_chattester_typebugs_non_buggy.jsonl'),
        'symprompt': os.path.join(base_res_dir, '0501_symprompt_typebugs_non_buggy.jsonl'),
        'hits': os.path.join(base_res_dir, '0501_hits_typebugs_non_buggy.jsonl'),
        'our_iterative_no_rethink': os.path.join(base_res_dir, 'typebugs','0502_our_no_rethink_iterative_non_buggy.jsonl'),
        'our_seperate_no_rethink': os.path.join(base_res_dir, 'typebugs','0502_our_no_rethink_seperate_non_buggy.jsonl'),
        # 'our_iterative': os.path.join(base_res_dir, 'typebugs','0502_our_iterative_non_buggy.jsonl'),
        # 'our_seperate': os.path.join(base_res_dir, 'typebugs','0502_our_seperate_non_buggy.jsonl')
        'our_iterative': os.path.join(base_res_dir, 'typebugs','0515_our_iterative_typebugs_non_buggy.jsonl'),
        'our_seperate': os.path.join(base_res_dir, 'typebugs','0515_our_seperate_typebugs_non_buggy.jsonl')
    }
}

def print_combined_chain_res(combined_chain_res):
    print(combined_chain_res["tp"])
    print(combined_chain_res["fp"])
    print(f'combined_chain all bugs: {len(combined_chain_res["all_bugs"])}')
    print(f'combined_chain tp: {len(combined_chain_res["tp"])}')
    print(f'combined_chain fp: {len(combined_chain_res["fp"])}')
    print(f'combined_chain fn: {len(combined_chain_res["fn"])}')
    print(f'combined_chain tn: {len(combined_chain_res["tn"])}')

def combine_two_res(all_bugs, res1, res2):
    new_fps = res2['fp'].intersection(res1['tn'])
    new_fps = res1['fp'].union(new_fps)
    # res2['fp'].union(res1['fp'])
    new_tps = res1['tp'].difference(new_fps)
    
    new_tns = res2['tn'].difference(new_fps)

    combined_res = {}
    combined_res['all_bugs'] = all_bugs
    combined_res['tp'] = new_tps
    combined_res['fp'] = new_fps
    combined_res['fn'] = res1['fn']
    combined_res['tn'] = new_tns
    return combined_res


if __name__ == '__main__':
    run_datasets = ['bugs_in_py', 'typebugs']
    # run_datasets = ['bugs_in_py']
    approaches = ['chat_tester', 'symprompt', 'hits', 'our_iterative_no_rethink', 'our_seperate_no_rethink', 'our_iterative', 'our_seperate']

    total_reses = defaultdict()
    for single_dataset in run_datasets:
        print(f'================= {single_dataset} =================')
        all_reses = defaultdict()
        for single_approach in approaches:
            res_file = dataset_config[single_dataset][single_approach]

            with open(res_file, 'r') as f:
                lines = f.readlines()
            
            total = len(lines)
            
            all_bugs = set()
            has_with_bugs = set()
            tp = set()
            fp = set()
            fn = set()
            tn = set()
            
            for line in lines:
                data = json.loads(line)
                proj_name = data['proj_name']
                bug_id = data['bug_id']
                
                identifier = f'{proj_name}_{bug_id}'
                
                if identifier in ['pandas_49', 'luigi_14', 'numpy_numpy-9999_arraysetops', 'pandas_pandas-22072_categorical', 'numpy_numpy-10473_polynomial', 'pandas_pandas-22378_ops']:
                    continue
                
                all_test_res = data['test_reses']
                
                if all_test_res:
                    all_bugs.add(identifier)
                else:
                    continue
                
                all_test_status = []
                for single_res in all_test_res:
                    focal_type_error = single_res['focal_type_error']
                    fixed_type_error = single_res['fixed_type_error']
                    
                    if fixed_type_error:
                        all_test_status.append('fp')
                    else:
                        all_test_status.append('tn')

                if any([i == 'fp' for i in all_test_status]):
                    fp.add(identifier)
                    continue
                elif any([i == 'tn' for i in all_test_status]):
                    tn.add(identifier)
                    continue
                else:
                    continue

            all_reses[single_approach] = {
                'total': total,
                'all_bugs': all_bugs,
                'tp': tp,
                'fp': fp,
                'fn': fn,
                'tn': tn
            }
        
        all_bugs = all_reses['our_iterative']['all_bugs'].union(all_reses['our_seperate']['all_bugs']).union(all_reses['our_iterative_no_rethink']['all_bugs']).union(all_reses['our_seperate_no_rethink']['all_bugs'])

        for single_approach, single_res in all_reses.items():
            single_res['all_bugs'] = all_bugs
            single_res['tp'] = set()
            single_res['fp'] = single_res['fp'].intersection(all_bugs)
            single_res['tn'] = all_bugs.difference(single_res['fp'])
            single_res['fn'] = set()
            
        for single_approach, single_res in all_reses.items():
            print('=' * 20)
            tp = single_res['tp']
            fp = single_res['fp']
            fn = single_res['fn']
            tn = single_res['tn']
            print(f'{single_approach} all bugs: {len(all_bugs)}')
            print(f'{single_approach} tp: {len(tp)}')
            print(f'{single_approach} fp: {len(fp)}')
            print(f'{single_approach} fn: {len(fn)}')
            print(f'{single_approach} tn: {len(tn)}')
            print(fp)
            # print(fn)
            print('=' * 20)
        
        all_reses['combined_chain'] = combine_two_res(all_bugs, all_reses['our_iterative_no_rethink'], all_reses['our_seperate_no_rethink'])
        
        print('=' * 10 + 'combined chain' + '=' * 10)
        print_combined_chain_res(all_reses['combined_chain'])
        
        all_reses['combined_rethink_chain'] = combine_two_res(all_bugs, all_reses['our_iterative'], all_reses['our_seperate'])
        
        print('=' * 10 + 'combined rethink chain' + '=' * 10)
        print_combined_chain_res(all_reses['combined_rethink_chain'])
        
        print(f'================= {single_dataset} Ends=================')

        total_reses[single_dataset] = all_reses

    # run_datasets = ['bugs_in_py', 'typebugs']
    # metrics = ['tp', 'fp', 'fn', 'tn']
    # approaches = ['chat_tester', 'our_repair_chain_iterative', 'our_repair_chain_seperate', 'our_repair_rethink_chain_iterative', 'our_repair_rethink_chain_seperate']
    
    # header = ['App.', 'BugsInPy', '', '', '', 'TypeBugs', '', '', '']
    # res_table = [header]
    # for single_approach in approaches:
    #     single_app_res = [single_approach]
    #     for single_dataset in run_datasets:
    #         for single_metric in metrics:
    #             single_app_res.append(len(total_reses[single_dataset][single_approach][single_metric]))
    #     res_table.append(single_app_res)
    
    # for i in res_table:
    #     print(i)
    # print(res_table)
                
