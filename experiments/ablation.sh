#!/usr/bin/env bash
# =============================================================================
# 3-arm ablation at GAMMA-paper fidelity (populations=200, generations=50,
# edge platform: 168 PEs / SL=512B / SG=108KB), ALL LAYERS of each model.
#
#   base    - no filter, every genome evaluated (the paper's GAMMA)
#   qlearn  - learned evaluation filter
#   random  - CONTROL ARM: same skip rate, no learning
#
# The control arm is the point. If qlearn cannot beat random, the Q-table
# is contributing nothing.
#
# COST: ~115 s per layer on 12 cores at paper settings.
#   TIER1 (6 models,  82 layers, 3 arms, 1 seed) ~  8 h
#   TIER2 (18 models,735 layers, 3 arms, 1 seed) ~ 70 h
#   Scales roughly with core count -- a 64-core box does TIER2 in ~13 h.
#
# Usage:
#   bash experiments/ablation.sh                        # TIER1 (default)
#   TIER=2 bash experiments/ablation.sh                 # all 18 models
#   MODELS="alexnet vgg16" SEEDS="42 7" bash experiments/ablation.sh
#
# Resumable: re-running skips only runs that completed cleanly.
# Run models SEQUENTIALLY -- each run already uses every core via its pool.
# =============================================================================
set -u
cd "$(dirname "$0")/../src/GAMMA"
OUT="../../experiments/results"; mkdir -p "$OUT"

TIER="${TIER:-1}"
if [ "$TIER" = "2" ]; then
  DEFAULT_MODELS="resnet18 resnet50 vgg16 alexnet googlenet densenet squeezenet \
wide_resnet50 resnext50_32x4d shufflenet_v2 mobilenet_v2 mnasnet \
BERT_m ALBERT_m T5_m transformer dlrmRMC1_m ncf_m"
else
  # representative subset: CNN large-kernel, CNN small-kernel, deep CNN,
  # NLP transformer, recommendation -- 82 layers total
  DEFAULT_MODELS="alexnet vgg16 resnet18 squeezenet BERT_m ncf_m"
fi

MODELS="${MODELS:-$DEFAULT_MODELS}"
SEEDS="${SEEDS:-42}"
SKIP_FRAC="${SKIP_FRAC:-0.35}"
POP="${POP:-200}"; GEN="${GEN:-50}"          # GAMMA paper settings
NUM_PE=168; L1=512; L2=108000                # GAMMA paper, edge platform

COMMON="--num_pop $POP --epochs $GEN --num_layer 0 --num_pe $NUM_PE --l1_size $L1 --l2_size $L2"

for M in $MODELS; do
  for S in $SEEDS; do
    for ARM in base qlearn random; do
      TAG="${M}_s${S}_${ARM}"; LOG="$OUT/${TAG}.log"
      # Require the whole-model summary, not just /usr/bin/time's line --
      # time writes its output even when the run crashes.
      if grep -q "MODEL TOTAL" "$LOG" 2>/dev/null; then echo "[skip] $TAG"; continue; fi
      case $ARM in
        base)   EXTRA="" ;;
        qlearn) EXTRA="--use_qfilter --filter_mode qlearn --skip_frac $SKIP_FRAC" ;;
        random) EXTRA="--use_qfilter --filter_mode random --skip_frac $SKIP_FRAC" ;;
      esac
      echo "[run ] $TAG  ($(date '+%H:%M:%S'))"
      /usr/bin/time -f "REAL_TIME_S=%e USER_TIME_S=%U SYS_TIME_S=%S" \
        python3 main.py --model "$M" $COMMON --seed "$S" $EXTRA \
        --outdir "experiments/results/${TAG}_out" > "$LOG" 2>&1 \
        || echo "[FAIL] $TAG -- see $LOG"
    done
  done
done
echo "done -> python3 experiments/summarize.py"
