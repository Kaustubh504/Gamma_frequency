#!/bin/bash

cd ./src/GAMMA

# The values we want to test
DECAYS=(0.85 0.90 0.98)
ALPHAS=(0.1 0.5)

echo "======================================================="
echo "🧪 STARTING HYPERPARAMETER GRID SEARCH"
echo "======================================================="

for decay in "${DECAYS[@]}"; do
    for alpha in "${ALPHAS[@]}"; do
        
        # Create a unique output folder name for this combination
        OUT_DIR="outdir_tune_decay${decay}_alpha${alpha}"
        
        echo "-------------------------------------------------------"
        echo "▶️ RUNNING: Epsilon Decay = $decay | Alpha = $alpha"
        echo "-------------------------------------------------------"
        
        # Drop OS caches to ensure fair time comparisons
        sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches' 2>/dev/null
        
        time python3 main.py \
            --fitness1 latency --fitness2 power --num_pe 168 \
            --l1_size 512 --l2_size 108000 --NocBW 81920000 \
            --epochs 100 --model resnet18 --num_layer 1 \
            --use_qfilter --q_table_size 5000 \
            --q_alpha $alpha --epsilon_decay $decay \
            --outdir $OUT_DIR > "../${OUT_DIR}_log.txt" 2>&1
            
        echo "✅ Finished. Logs saved to ${OUT_DIR}_log.txt"
        
    done
done

cd ../../
echo "🎉 ALL EXPERIMENTS COMPLETED!"