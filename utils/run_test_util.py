from io import StringIO
import os
import json
from data.configurations import code_base
import subprocess


def assemble_test_file(module_dir, module_name, index, processed_imports, test_case):
    tmp_name = module_name.replace('.', '_')
    test_file = os.path.join(module_dir, f'test_case_{tmp_name}_{index}.py')
    test_content = StringIO('')
    
    for imp in processed_imports:
        test_content.write(f'{imp}\n')
        
    test_content.write('\n')
    test_content.write('class Test(unittest.TestCase):\n')

    test_content.write('\n    @timeout_decorator.timeout(1)\n')
    for line in test_case.split('\n'):
        test_content.write(f'    {line}\n')

    test_content.write('\nif __name__ == "__main__":\n')
    test_content.write('    unittest.main()\n')
    
    final_content = test_content.getvalue()
    test_content.close()
    
    with open(test_file, 'w') as f:
        f.write(final_content)
    return test_file, final_content

def write_test_file(module_dir , new_test_file, test_case):
    test_file_location = os.path.join(module_dir, new_test_file)
    
    with open(test_file_location, 'w') as f:
        f.write(test_case)
    return test_file_location, test_case


def run_test_and_collect_cov_lightweight(module_dir, test_file, relative_test_file, used_framework, module_tmp_dir, python_bin):
    original_dir_and_files = os.listdir(module_dir)

    if os.path.exists(module_tmp_dir):
        os.system(f'rm -rf {module_tmp_dir}')
    
    os.makedirs(module_tmp_dir)

    permission = 0o555
    try:
        # 修改文件夹的权限
        os.chmod(code_base, permission)
        print("成功设置父文件夹的不可删除权限！")
    except OSError:
        print("设置父文件夹的权限失败！")

    os.chdir(module_dir)
    relative_test_name = relative_test_file.replace('/', '.').replace('.py', '')
    
    if used_framework == 'unittest':
        cmd = f'{python_bin} -m unittest {relative_test_name}'
    elif used_framework == 'pytest':
        cmd = f'{python_bin} -m pytest {relative_test_file}'
    elif used_framework == 'py.test':
        cmd = f'py.test {relative_test_file}'
    else:
        raise ValueError("Unsupported testing framework. Please use 'unittest' or 'pytest'.")
    
    # cmd = f'{python_bin} {test_file}'
    cmd = 'PYTHONPATH=./ timeout 60 ' + cmd
    process_output = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
    run_output = process_output.stdout + process_output.stderr

    for thing in os.scandir(module_dir):
        if thing.name in original_dir_and_files:
            continue
        else:
            if 'test_case_' not in thing.name:
                os.system('rm -r ' + thing.name)
                
    os.system(f'rm {test_file}')
    return run_output, process_output.stdout, process_output.stderr

    
def is_triggered(focal_output, fixed_output):
    focal_passed = True
    fixed_passed = True
    focal_type_error = False
    fixed_type_error = False
    triggered = False
    if 'error' in focal_output.lower():
        focal_passed = False
    if 'error' in fixed_output.lower():
        fixed_passed = False
    
    processed_focal_output = focal_output.replace('(TypeError)', '')
    processed_focal_output = processed_focal_output.replace('DID NOT RAISE <class \'TypeError\'>', '')
    processed_focal_output = processed_focal_output.replace('trigger TypeError', '')
    processed_focal_output = processed_focal_output.replace('a TypeError', '')
    processed_focal_output = processed_focal_output.replace('TypeError\"\"\"', '')
    
    processed_fixed_output = fixed_output.replace('(TypeError)', '')
    processed_fixed_output = processed_fixed_output.replace('DID NOT RAISE <class \'TypeError\'>', '')
    processed_fixed_output = processed_fixed_output.replace('trigger TypeError', '')
    processed_fixed_output = processed_fixed_output.replace('a TypeError', '')
    processed_fixed_output = processed_fixed_output.replace('TypeError\"\"\"', '')
    
    if ': TypeError' in processed_focal_output or 'TypeError:' in processed_focal_output:
        focal_type_error = True
        
    if ': TypeError' in processed_fixed_output or 'TypeError:' in processed_fixed_output:
        fixed_type_error = True
        
    if focal_type_error and not fixed_type_error:
        triggered = True
    return  triggered, focal_type_error, fixed_type_error, focal_passed, fixed_passed
    