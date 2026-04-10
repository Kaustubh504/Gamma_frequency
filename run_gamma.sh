# cd ./src/GAMMA
# python3 main.py --fitness1 latency --fitness2 power --num_pe 168 --l1_size 512 --l2_size 108000 --NocBW 81920000 --epochs 10 \
#               --model vgg16 --num_layer 1
# cd ../../





#!/bin/bash

# cd ./src/GAMMA
# python3 main.py --fitness1 latency --fitness2 power --num_pe 168 \
#                 --l1_size 512 --l2_size 108000 --NocBW 81920000 \
#                 --epochs 10 --model vgg16 --num_layer 1 \
#                 --use_qfilter --q_table_size 5000 --q_alpha 0.1 --q_gamma 0.9
# cd ../../

# cd ./src/GAMMA

# # 1. RUN BASELINE (Normal Run without Q-Filter)
# python3 main.py --fitness1 latency --fitness2 power --num_pe 168 \
#                 --l1_size 512 --l2_size 108000 --NocBW 81920000 \
#                 --epochs 10 --model vgg16 --num_layer 1 \
#                 --outdir outdir_baseline

# # 2. RUN OPTIMIZED (With Q-Filter)
# python3 main.py --fitness1 latency --fitness2 power --num_pe 168 \
#                 --l1_size 512 --l2_size 108000 --NocBW 81920000 \
#                 --epochs 10 --model vgg16 --num_layer 1 \
#                 --use_qfilter --q_table_size 5000 --q_alpha 0.1 --q_gamma 0.9 \
#                 --outdir outdir_qfilter

# cd ../../

# cd ./src/GAMMA

# echo "====================================="
# echo "🏃‍♂️ RUNNING BASELINE (NO Q-FILTER)..."
# echo "====================================="
# time python3 main.py --fitness1 latency --fitness2 power --num_pe 168 \
#                 --l1_size 512 --l2_size 108000 --NocBW 81920000 \
#                 --epochs 10 --model vgg16 --num_layer 1 \
#                 --outdir outdir_baseline

# echo "====================================="
# echo "🚀 RUNNING OPTIMIZED (WITH Q-FILTER)..."
# echo "====================================="
# time python3 main.py --fitness1 latency --fitness2 power --num_pe 168 \
#                 --l1_size 512 --l2_size 108000 --NocBW 81920000 \
#                 --epochs 10 --model vgg16 --num_layer 1 \
#                 --use_qfilter --q_table_size 5000 --q_alpha 0.1 --q_gamma 0.9 \
#                 --outdir outdir_qfilter

# cd ../../

## 20 epochs run

# cd ./src/GAMMA

# echo "======================================================="
# echo " RUNNING BASELINE (NO Q-FILTER) - ResNet18 / 20 Epochs"
# echo "======================================================="
# time python3 main.py --fitness1 latency --fitness2 power --num_pe 168 \
#                 --l1_size 512 --l2_size 108000 --NocBW 81920000 \
#                 --epochs 200 --model resnet18 --num_layer 1 \
#                 --outdir outdir_baseline_v2

# echo "======================================================="
# echo " RUNNING OPTIMIZED (Q-FILTER) - ResNet18 / 20 Epochs"
# echo "======================================================="
# time python3 main.py --fitness1 latency --fitness2 power --num_pe 168 \
#                 --l1_size 512 --l2_size 108000 --NocBW 81920000 \
#                 --epochs 200 --model resnet18 --num_layer 1 \
#                 --use_qfilter --q_table_size 5000 --q_alpha 0.1 --q_gamma 0.9 \
#                 --outdir outdir_qfilter_v2

# cd ../../

## 100 epochs run


cd ./src/GAMMA

# Optional but highly recommended: Force Linux to drop its disk caches before starting!
# (Requires sudo, skip this specific command if you don't have root access)
sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'

echo "======================================================="
echo " RUNNING OPTIMIZED (Q-FILTER) FIRST - COLD START"
echo "======================================================="
# time python3 main.py --fitness1 latency --fitness2 power --num_pe 168 \
#                 --l1_size 512 --l2_size 108000 --NocBW 81920000 \
#                 --epochs 200 --model resnet18 --num_layer 1 \
#                 --use_qfilter --q_table_size 5000 --q_alpha 0.5 --q_gamma 0.9 \
#                 --outdir outdir_qfilter_cold
time python3 main.py --fitness1 latency --fitness2 power --num_pe 168 \
                --l1_size 512 --l2_size 108000 --NocBW 81920000 \
                --epochs 200 --model vgg16 --num_layer 1 \
                --use_qfilter --q_table_size 5000 \
                --q_alpha 0.5 --q_gamma 0.9 --epsilon_decay 0.98 \
                --outdir outdir_final_run

echo "======================================================="
echo "🏃 RUNNING BASELINE (NO Q-FILTER) SECOND - WARM CACHE"
echo "======================================================="
time python3 main.py --fitness1 latency --fitness2 power --num_pe 168 \
                --l1_size 512 --l2_size 108000 --NocBW 81920000 \
                --epochs 200 --model vgg16 --num_layer 1 \
                --outdir outdir_baseline_warm

cd ../../

# ./run_gamma.sh 2>&1 | tee full_log.txt

# vary the q table size and episilon see the effect of cpu time and clock cycle and reward. Find the optimal values for each model.
# make excel file for different models without q filter and with q filter.
# describe the different fields of the q table.
# set the epoch as per the paper.