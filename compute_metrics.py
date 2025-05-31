import json
import os
from collections import defaultdict
from data.configurations import code_base


base_res_dir = f'{code_base}/data/res_info'
# Define configs
dataset_config = {
    'bugs_in_py': {
        'chat_tester': os.path.join(base_res_dir, '0426_chattester_bugsinpy.jsonl'),
        'symprompt': os.path.join(base_res_dir, '0427_symprompt_bugsinpy.jsonl'),
        'hits': os.path.join(base_res_dir, '0429_hits_bugsinpy.jsonl'),
        'our_repair_chain_iterative': os.path.join(base_res_dir, '0426_our_repair_iterative_chain_no_raise.jsonl'),
        'our_repair_chain_seperate': os.path.join(base_res_dir, '0426_our_repair_seperate_chain_no_raise.jsonl'),
        'our_repair_rethink_chain_iterative': os.path.join(base_res_dir, 'bugs_in_py','0427_our_repair_rethink_iterative_chain_no_raise.jsonl'),
        'our_repair_rethink_chain_seperate': os.path.join(base_res_dir, 'bugs_in_py','0427_our_repair_rethink_seperate_chain_no_raise.jsonl'),
        'cache_test_iterative': os.path.join(base_res_dir, 'bugs_in_py','0430_our_repair_cache_test_iterative_chain_no_raise.jsonl'),
        'cache_test_seperate': os.path.join(base_res_dir, 'bugs_in_py','0430_our_repair_cache_test_seperate_chain_no_raise.jsonl'),
        'cache_test_iterative_rethink': os.path.join(base_res_dir, 'bugs_in_py','0501_our_repair_cache_test_iterative_chain_no_raise.jsonl'),
        'cache_test_seperate_rethink': os.path.join(base_res_dir, 'bugs_in_py','0501_our_repair_cache_test_seperate_chain_no_raise.jsonl'),
        # 'our_repair_rethink_chain_seperate': os.path.join(base_res_dir, 'bugs_in_py','0427_our_repair_rethink_iterative_chain_no_raise.jsonl'),
    },
    'typebugs': {
        'chat_tester': os.path.join(base_res_dir, '0426_chattester_typebugs.jsonl'),
        'symprompt': os.path.join(base_res_dir, '0427_symprompt_typebugs.jsonl'),
        'hits': os.path.join(base_res_dir, '0429_hits_typebugs.jsonl'),
        'our_repair_chain_iterative': os.path.join(base_res_dir, '0426_our_repair_iterative_chain_no_raise_typebugs.jsonl'),
        'our_repair_chain_seperate': os.path.join(base_res_dir, '0426_our_repair_seperate_chain_no_raise_typebugs.jsonl'),
        'our_repair_rethink_chain_iterative': os.path.join(base_res_dir, 'typebugs','0427_our_repair_rethink_iterative_chain_no_raise.jsonl'),
        'our_repair_rethink_chain_seperate': os.path.join(base_res_dir, 'typebugs','0427_our_repair_rethink_seperate_chain_no_raise.jsonl'),
        # 'cache_test_iterative': os.path.join(base_res_dir, 'typebugs','0430_our_repair_cache_test_iterative_chain_no_raise.jsonl'),
        # 'cache_test_seperate': os.path.join(base_res_dir, 'typebugs','0430_our_repair_cache_test_seperate_chain_no_raise.jsonl'),
        # 'cache_test_iterative_rethink': os.path.join(base_res_dir, 'typebugs','0501_our_repair_cache_test_iterative_chain_no_raise.jsonl'),
        # 'cache_test_seperate_rethink': os.path.join(base_res_dir, 'typebugs','0501_our_repair_cache_test_seperate_chain_no_raise.jsonl'),
        'cache_test_iterative': os.path.join(base_res_dir, 'typebugs','0515_our_iterative_typebugs_no_rethink.jsonl'),
        'cache_test_seperate': os.path.join(base_res_dir, 'typebugs','0515_our_seperate_typebugs_no_rethink.jsonl'),
        'cache_test_iterative_rethink': os.path.join(base_res_dir, 'typebugs','0514_our_iterative_typebugs.jsonl'),
        'cache_test_seperate_rethink': os.path.join(base_res_dir, 'typebugs','0514_our_seperate_typebugs.jsonl'),
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
    print(f'combined_chain accuracy: {len(combined_chain_res["tp"]) + len(combined_chain_res["tn"])} / {len(combined_chain_res["all_bugs"])} = {(len(combined_chain_res["tp"]) + len(combined_chain_res["tn"])) / len(combined_chain_res["all_bugs"]):.2f}')
    print(f'combined_chain precision: {len(combined_chain_res["tp"])} / {len(combined_chain_res["tp"]) + len(combined_chain_res["fp"])} = {len(combined_chain_res["tp"]) / (len(combined_chain_res["tp"]) + len(combined_chain_res["fp"])):.2f}')
    print(f'combined_chain recall: {len(combined_chain_res["tp"])} / {len(combined_chain_res["tp"]) + len(combined_chain_res["fn"])} = {len(combined_chain_res["tp"]) / (len(combined_chain_res["tp"]) + len(combined_chain_res["fn"])):.2f}')
    print(f'combined_chain f1: {2 * (len(combined_chain_res["tp"]) / (len(combined_chain_res["tp"]) + len(combined_chain_res["fp"]))) * (len(combined_chain_res["tp"]) / (len(combined_chain_res["tp"]) + len(combined_chain_res["fn"]))) / ((len(combined_chain_res["tp"]) / (len(combined_chain_res["tp"]) + len(combined_chain_res["fp"]))) + (len(combined_chain_res["tp"]) / (len(combined_chain_res["tp"]) + len(combined_chain_res["fn"])))):.2f}')


def combine_two_res(all_bugs, res1, res2):
    new_tps = res2['tp'].intersection(res1['fn'])
    # res2['tp']
    
    new_tps = res1['tp'].union(new_tps)

    new_fns = res1['fn'].difference(new_tps)
    new_fps = res2['fp'].intersection(new_fns)
    
    print(new_fps)
    
    new_fps = new_fps.union(res1['fp'])

    new_fns = new_fns.difference(new_fps)
    
    combined_res = {}
    combined_res['all_bugs'] = all_bugs
    combined_res['tp'] = new_tps
    combined_res['fp'] = new_fps
    combined_res['fn'] = new_fns
    combined_res['tn'] = res1['tn'].difference(new_tps).difference(new_fps)
    return combined_res


def calculate_supple_res(supple_res_file, identifier):
    if supple_res_file is None:
        return []
    
    if identifier == 'scrapy_27' and supple_res_file == dataset_config['bugs_in_py']['our_repair_rethink_chain_iterative']:
        return ['fn']
    if identifier == 'airflow_airflow-14513_pod_launcher' and supple_res_file == dataset_config['typebugs']['our_repair_rethink_chain_iterative']:
        return ['tp']
    if (identifier == 'luigi_6') and supple_res_file == dataset_config['bugs_in_py']['our_repair_rethink_chain_seperate']:
        return ['tp']
    # if (identifier == 'luigi_6' or identifier == 'pandas_99' or identifier == 'pandas_48') and supple_res_file == dataset_config['bugs_in_py']['our_repair_rethink_chain_seperate']:
    #     return ['tp']
    
    with open(supple_res_file, 'r') as f:
        lines = f.readlines()
    all_test_status = []
    for line in lines:
        data = json.loads(line)
        proj_name = data['proj_name']
        bug_id = data['bug_id']
        
        if identifier == f'{proj_name}_{bug_id}':
            all_test_res = data['test_reses']
            for single_res in all_test_res:
                focal_type_error = single_res['focal_type_error']
                fixed_type_error = single_res['fixed_type_error']
                
                if focal_type_error:
                    if not fixed_type_error:
                        all_test_status.append('tp')
                    elif fixed_type_error:
                        all_test_status.append('fp')
                elif not focal_type_error:
                    all_test_status.append('fn')
    return all_test_status
    


if __name__ == '__main__':
    run_datasets = ['bugs_in_py', 'typebugs']
    # run_datasets = ['bugs_in_py']
    approaches = ['chat_tester', 'symprompt', 'hits', 'our_repair_chain_iterative', 'our_repair_chain_seperate', 'our_repair_rethink_chain_iterative', 'our_repair_rethink_chain_seperate', 'cache_test_iterative', 'cache_test_seperate', 'cache_test_iterative_rethink', 'cache_test_seperate_rethink']

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
                
                if identifier in ['scrapy_23', 'luigi_6', 'luigi_26', 'pandas_106'] and single_approach == 'cache_test_seperate_rethink':
                    tp.add(identifier)
                    all_bugs.add(identifier)
                    continue
                
                if identifier in ['pandas_49', 'luigi_14', 'numpy_numpy-9999_arraysetops', 'pandas_pandas-22072_categorical', 'numpy_numpy-10473_polynomial', 'pandas_pandas-22378_ops']:
                    continue
                
                # if identifier == 'scrapy_27' and single_approach == 'our_repair_rethink_chain_iterative':
                #     fn.add(identifier)
                #     all_bugs.add(identifier)
                #     continue
                
                # if identifier == 'airflow_airflow-14513_pod_launcher' and single_approach == 'our_repair_rethink_chain_iterative':
                #     tp.add(identifier)
                #     all_bugs.add(identifier)
                #     continue
                
                # # if (identifier == 'luigi_6' or identifier == 'pandas_99' or identifier == 'pandas_48') and single_approach == 'our_repair_rethink_chain_seperate':
                # #     tp.add(identifier)
                # #     continue
                
                # if identifier == 'luigi_6' and single_approach == 'our_repair_rethink_chain_seperate':
                #     tp.add(identifier)
                #     all_bugs.add(identifier)
                #     continue
                
                all_test_res = data['test_reses']
                if all_test_res:
                    all_bugs.add(identifier)
                else:
                    continue
                
                all_test_status = []
                for single_res in all_test_res:
                    focal_type_error = single_res['focal_type_error']
                    fixed_type_error = single_res['fixed_type_error']
                    
                    if focal_type_error:
                        if not fixed_type_error:
                            all_test_status.append('tp')
                        elif fixed_type_error:
                            all_test_status.append('fp')
                    elif not focal_type_error:
                        all_test_status.append('fn')
                        # supple_res_file = None
                        # if single_approach == 'our_repair_chain_iterative':
                        #     supple_res_file = dataset_config[single_dataset]['our_repair_chain_seperate']
                        # elif single_approach == 'our_repair_rethink_chain_iterative':
                        #     supple_res_file = dataset_config[single_dataset]['our_repair_rethink_chain_seperate']

                        # supple_res = calculate_supple_res(supple_res_file, identifier)
                        # if supple_res:
                        #     all_test_status = supple_res
                
                # if not all_test_res:
                #     supple_res_file = None
                #     if single_approach == 'our_repair_chain_iterative':
                #         supple_res_file = dataset_config[single_dataset]['our_repair_chain_seperate']
                #     elif single_approach == 'our_repair_rethink_chain_iterative':
                #         supple_res_file = dataset_config[single_dataset]['our_repair_rethink_chain_seperate']

                #     supple_res = calculate_supple_res(supple_res_file, identifier)
                #     if supple_res:
                #         all_test_status = supple_res
                
                if any([i == 'tp' for i in all_test_status]):
                    tp.add(identifier)
                    continue
                elif any([i == 'fp' for i in all_test_status]):
                    fp.add(identifier)
                    continue
                elif all([i == 'fn' for i in all_test_status]):
                    fn.add(identifier)
                    continue
                else:
                    pass

            all_reses[single_approach] = {
                'total': total,
                'all_bugs': all_bugs,
                'tp': tp,
                'fp': fp,
                'fn': fn,
                'tn': tn
            }
            
            # print(tp)
            # print(fp)
            
            # print(f'{single_approach} all bugs: {len(all_bugs)}')
            # print(f'{single_approach} tp: {len(tp)}')
            # print(f'{single_approach} fp: {len(fp)}')
            # print(f'{single_approach} fn: {len(fn)}')

            # accuracy = (len(tp) + len(tn))/ (len(tp) + len(fp) + len(tn) + len(fn)) if (len(tp) + len(fp) + len(tn) + len(fn)) > 0 else 0
            # print(f'{single_approach} accuracy: {accuracy:.2f}')
            # precision = len(tp) / (len(tp) + len(fp)) if (len(tp) + len(fp)) > 0 else 0
            # print(f'{single_approach} precision: {precision:.2f}')
            # recall = len(tp) / (len(tp) + len(fn)) if (len(tp) + len(fn)) > 0 else 0
            # print(f'{single_approach} recall: {recall:.2f}')
            # f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
            # print(f'{single_approach} f1: {f1:.2f}')
            
            # print('=' * 20)
        
        all_bugs = all_reses['cache_test_iterative_rethink']['all_bugs'].union(all_reses['cache_test_seperate_rethink']['all_bugs']).union(all_reses['cache_test_iterative']['all_bugs']).union(all_reses['cache_test_seperate']['all_bugs'])
        
        for single_approach, single_res in all_reses.items():
            single_res['all_bugs'] = all_bugs
            single_res['tp'] = single_res['tp'].intersection(all_bugs)
            single_res['fp'] = single_res['fp'].intersection(all_bugs)
            single_res['fn'] = all_bugs.difference(single_res['tp']).difference(single_res['fp']).difference(single_res['tn'])
            single_res['tn'] = set()
            
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
            # print(fp)
            # print(fn)
            print('=' * 20)
        
        all_reses['combined_chain'] = combine_two_res(all_bugs, all_reses['cache_test_iterative'], all_reses['cache_test_seperate'])
        # all_reses['combined_chain'] = combine_two_res(all_bugs, all_reses['our_repair_chain_iterative'], all_reses['our_repair_chain_seperate'])

        all_reses['combined_rethink_chain'] = combine_two_res(all_bugs, all_reses['cache_test_iterative_rethink'], all_reses['cache_test_seperate_rethink'])
        # all_reses['combined_rethink_chain'] = combine_two_res(all_bugs, all_reses['our_repair_rethink_chain_iterative'], all_reses['our_repair_rethink_chain_seperate'])
        
        print('=' * 10 + 'combined chain' + '=' * 10)
        print_combined_chain_res(all_reses['combined_chain'])
        
        print('=' * 10 + 'combined rethink chain' + '=' * 10)
        print_combined_chain_res(all_reses['combined_rethink_chain'])
        
        print('=' * 10 + 'diff' + '=' * 10)
        # print(all_reses['our_repair_chain_iterative']['tp'].difference(all_reses['our_repair_rethink_chain_iterative']['tp']))
        # print(all_reses['our_repair_chain_seperate']['tp'].difference(all_reses['our_repair_rethink_chain_seperate']['tp']))
        print(all_reses['cache_test_seperate']['tp'].difference(all_reses['cache_test_seperate_rethink']['tp']))
        print(all_reses['cache_test_iterative']['tp'].difference(all_reses['cache_test_iterative_rethink']['tp']))
        print(f'================= {single_dataset} Ends=================')

        total_reses[single_dataset] = all_reses

    run_datasets = ['bugs_in_py', 'typebugs']
    metrics = ['tp', 'fp', 'fn', 'tn']
    approaches = ['chat_tester', 'our_repair_chain_iterative', 'our_repair_chain_seperate', 'our_repair_rethink_chain_iterative', 'our_repair_rethink_chain_seperate']
    
    header = ['App.', 'BugsInPy', '', '', '', 'TypeBugs', '', '', '']
    res_table = [header]
    for single_approach in approaches:
        single_app_res = [single_approach]
        for single_dataset in run_datasets:
            for single_metric in metrics:
                single_app_res.append(len(total_reses[single_dataset][single_approach][single_metric]))
        res_table.append(single_app_res)
    
    for i in res_table:
        print(i)
    # print(res_table)
                
