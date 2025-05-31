from glob import glob
import chardet
import os
import subprocess

env = os.environ.copy()

# 在同一个 shell 进程中执行 conda activate 并运行 which python
# command = "conda run -n llm which python"
# res = subprocess.run(command, text=True, capture_output=True, check=True, shell=True)
# print(res.stdout)


all_reqs = glob('/data/yangchen/llm_teut/data/benchmarks/bugsinpy/luigi/*/requirements.txt')
# /data/yangchen/llm_teut/data/benchmarks/bugsinpy/scrapy/scrapy-23/requirements.txt
for req in all_reqs:
    with open(req, "rb") as f:
        raw_data = f.read()

    encoding = chardet.detect(raw_data)["encoding"]
    print("Detected encoding:", encoding)

    new_reqs = []
    with open(req, "r", encoding=encoding) as f:
        original_reqs = f.readlines()
        for i, req_item in enumerate(original_reqs):
            if 'requests-async' in req_item:
                continue
            elif 'pywin32' in req_item:
                continue
            elif 'pypiwin32' in req_item:
                continue
            else:
                new_reqs.append(req_item)
                
    with open(req, 'w') as f:
        f.writelines(new_reqs)