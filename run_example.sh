#!/bin/bash

# conda remove -n pandas-33373_env --all --yes
# conda create -n pandas-33373_env python=3.7.9 --yes
# conda init bash
conda init
conda activate pandas-33373_env
conda info
# pip install -r /data/yangchen/llm_teut/data/benchmarks/typebugs/pandas/pandas-33373/requirements.txt

# cd /data/yangchen/llm_teut/data/typebugs/base_projects/pandas
# rm -rf /data/yangchen/llm_teut/data/typebugs/checkout_projects/pandas/pandas-33373__json/focal
# git checkout -f d857cd12b3ae11be788ba96015383a5b7464ecc9
# cp -r . /data/yangchen/llm_teut/data/typebugs/checkout_projects/pandas/pandas-33373__json/focal
# cd /data/yangchen/llm_teut/data/typebugs/checkout_projects/pandas/pandas-33373__json/focal
conda run -n pandas-41155_env /data/yangchen/llm_teut/data/benchmarks/typebugs/pandas/pandas-41155/dependency_setup.sh