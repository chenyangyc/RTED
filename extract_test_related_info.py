from data.configurations import bugs_in_py_info_file, typebugs_info_file, code_base
from collections import defaultdict
import json


all_reses = defaultdict()
with open(typebugs_info_file, 'r') as f:
    all_bug_data = json.load(f)

bug_test_related_info = f'{code_base}/data/benchmarks/test_related_info_typebugs.json'

all_info = defaultdict()

for bug_id, bug_info in all_bug_data.items():
    
    proj_name = bug_id.split('/')[0]
    bug_id = bug_id.split('/')[1]
    
    if proj_name not in all_info:
        all_info[proj_name] = defaultdict()

    
    test_files = bug_info['test_files']
    
    refactored_test_files = [i.replace('/', '.').replace('.py', '') for i in test_files]

    py_version =  bug_info['py_version']
    used_framework = ''
    
    test_shells = []
    with open(f'{code_base}/data/benchmarks/typebugs/{proj_name}/{bug_id}/test.sh', 'r') as f:
        for line in f:
            if line.strip() != '':
                test_shells.append(line.strip())
            
    test_shell = '\n'.join(test_shells)
    
    # test_shells = [i for i in test_shell.split('\n') if i != '']
    
    shell_to_file = defaultdict()
    
    shell_to_func = defaultdict()
    
    if '-m unittest' in test_shell:
        used_framework = 'unittest'

        for s in test_shells:
            for index, i in enumerate(refactored_test_files):
                if i in s:
                    shell_to_file[s] = test_files[index]
    
            if '::' in s: 
                test_func = s.split('::')[-1]
            else:
                test_func = ''
            shell_to_func[s] = test_func
                    
    elif 'pytest' in test_shell:
        used_framework = 'pytest'
        
        for s in test_shells:
            test_file = s.split('pytest ')[-1].split('.py')[0] + '.py'
            
            shell_to_file[s] = test_file
            
            if '::' in s: 
                test_func = s.split('::')[-1]
            else:
                test_func = ''
            shell_to_func[s] = test_func
                    
    elif 'py.test' in test_shell:
        used_framework = 'py.test'
        
        for s in test_shells:
            for index, i in enumerate(test_files):
                if i in s:
                    shell_to_file[s] = i
        
    all_info[proj_name][bug_id] = {
        'test_files': shell_to_file,
        'test_funcs': shell_to_func,
        'py_version': py_version,
        'used_framework': used_framework
    }

with open(bug_test_related_info, 'w') as f:
    json.dump(all_info, f, indent=4)
        

# all_reses = defaultdict()
# with open(bugs_in_py_info_file, 'r') as f:
#     all_bug_data = json.load(f)

# bug_test_related_info = f'{code_base}/data/benchmarks/test_related_info_bugsinpy.json'

# all_info = defaultdict()
# for proj_name, bugs in all_bug_data.items():

#     all_info[proj_name] = defaultdict()
    
#     for bug_id, bug_info in bugs.items():
        
#         test_files = bug_info['test_files']
#         test_funcs = bug_info['test_func']
        
#         refactored_test_files = [i.replace('/', '.').replace('.py', '') for i in test_files]

#         py_version =  bug_info['py_version']
#         used_framework = ''
        
#         test_shells = []
#         with open(f'{code_base}/data/benchmarks/bugsinpy/{proj_name}/{proj_name}-{bug_id}/test.sh', 'r') as f:
#             for line in f:
#                 test_shells.append(line.strip())
                
#         test_shell = '\n'.join(test_shells)
        
#         # test_shells = [i for i in test_shell.split('\n') if i != '']
        
#         shell_to_file = defaultdict()
        
#         shell_to_func = defaultdict()
        
#         for index, s in enumerate(test_shells):
#             shell_to_func[s] = test_funcs[index]
        
#         if '-m unittest' in test_shell:
#             used_framework = 'unittest'

#             for s in test_shells:
#                 for index, i in enumerate(refactored_test_files):
#                     if i in s:
#                         shell_to_file[s] = test_files[index]

#         elif 'pytest' in test_shell:
#             used_framework = 'pytest'
            
#             for s in test_shells:
#                 for index, i in enumerate(test_files):
#                     if i in s:
#                         shell_to_file[s] = i
                        
#         elif 'py.test' in test_shell:
#             used_framework = 'py.test'
            
#             for s in test_shells:
#                 for index, i in enumerate(test_files):
#                     if i in s:
#                         shell_to_file[s] = i
            
#         all_info[proj_name][bug_id] = {
#             'test_files': shell_to_file,
#             'test_funcs': shell_to_func,
#             'py_version': py_version,
#             'used_framework': used_framework
#         }

# with open(bug_test_related_info, 'w') as f:
#     json.dump(all_info, f, indent=4)
        