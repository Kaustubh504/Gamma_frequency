#!/usr/bin/env bash
# =============================================================================
# GAMMA Q-Filter ablation, run EXACTLY as specified in the GAMMA paper
# (Kao & Krishna, "GAMMA: Automating the HW Mapping of DNN Models on
#  Accelerators via Genetic Algorithm").
#
# Paper settings reproduced here:
#   * populations = 200, generations = 50   (paper 5.1: "we set the
#     populations=200, generations=50", giving the 10K samples/layer budget)
#   * ALL layers of each model              (paper 5.2: "the HW-mapping for
#     each of the 20 layers in ResNet-18")
#   * Edge platform, Table 2: 168 PEs, SL = 512B, SG = 108KB
#   * Target system, Table 3, default S1 (fixed aspect ratio, parallelism 2)
#     which is what the paper's per-layer ResNet-18 experiment uses.
#     SYSTEM=S2 -> flexible aspect ratio, parallelism 1 or 2 (Eyeriss-like)
#     SYSTEM=S3 -> scale-out, parallelism 2 or 3
#   * Objective: latency (paper 5.2.1). OBJ=energy gives paper 5.2.2.
#
# Arms:
#   base    original GAMMA, every genome evaluated
#   qlearn  GAMMA + Q-table evaluation filter
#   random  control: identical skip rate, no learning
#
# The `random` arm is what makes the claim falsifiable. "qlearn beats base"
# alone does not show the Q-table helped -- skipping anything saves calls.
# The Q-table has earned its place only if qlearn also beats random.
#
# COST: ~115 s per layer per arm on 12 cores. 735 layers x 3 arms ~ 70 h.
#       Scales with cores; a 64-core box is ~13 h. Fully resumable.
#
# Usage:
#   bash experiments/ablation.sh                     # all 18 models, S1, latency
#   SYSTEM=S2 bash experiments/ablation.sh
#   OBJ=energy bash experiments/ablation.sh
#   MODELS="resnet18" SEEDS="42 7 123" bash experiments/ablation.sh
# =============================================================================
set -u
cd "$(dirname "$0")/../src/GAMMA"
OUT="../../experiments/results"; mkdir -p "$OUT"

MODELS="${MODELS:-resnet18 resnet50 vgg16 alexnet googlenet densenet squeezenet \
wide_resnet50 resnext50_32x4d shufflenet_v2 mobilenet_v2 mnasnet \
BERT_m ALBERT_m T5_m transformer dlrmRMC1_m ncf_m}"
SEEDS="${SEEDS:-42}"
SKIP_FRAC="${SKIP_FRAC:-0.35}"
SYSTEM="${SYSTEM:-S1}"
OBJ="${OBJ:-latency}"

POP=200; GEN=50                       # paper 5.1
NUM_PE=168; L1=512; L2=108000         # paper Table 2, edge platform

case "$SYSTEM" in                     # paper Table 3
  S1) SYS="--slevel_min 2 --slevel_max 2 --fixedCluster 12" ;;   # 12x14 = 168
  S2) SYS="--slevel_min 1 --slevel_max 2 --fixedCluster 0"  ;;
  S3) SYS="--slevel_min 2 --slevel_max 3 --fixedCluster 0"  ;;
  *)  echo "SYSTEM must be S1, S2 or S3"; exit 1 ;;
esac
[ "$OBJ" = "energy" ] && FIT="--fitness1 energy --fitness2 latency" \
                      || FIT="--fitness1 latency --fitness2 energy"

COMMON="--num_pop $POP --epochs $GEN --num_layer 0 --num_pe $NUM_PE \
--l1_size $L1 --l2_size $L2 $SYS $FIT"

echo "system=$SYSTEM  objective=$OBJ  pop=$POP gen=$GEN  edge(168PE/512B/108KB)  all layers"
for M in $MODELS; do
  for S in $SEEDS; do
    for ARM in base qlearn random; do
      TAG="${M}_${SYSTEM}_${OBJ}_s${S}_${ARM}"; LOG="$OUT/${TAG}.log"
      # Require the whole-model summary. /usr/bin/time writes its line even on
      # a crash, so REAL_TIME_S alone is not proof the run finished.
      if grep -q "MODEL TOTAL" "$LOG" 2>/dev/null; then echo "[skip] $TAG"; continue; fi
      case $ARM in
        base)   E="" ;;
        qlearn) E="--use_qfilter --filter_mode qlearn --skip_frac $SKIP_FRAC" ;;
        random) E="--use_qfilter --filter_mode random --skip_frac $SKIP_FRAC" ;;
      esac
      echo "[run ] $TAG  ($(date '+%F %H:%M:%S'))"
      /usr/bin/time -f "REAL_TIME_S=%e USER_TIME_S=%U SYS_TIME_S=%S" \
        python3 main.py --model "$M" $COMMON --seed "$S" $E \
        --outdir "experiments/results/${TAG}_out" > "$LOG" 2>&1 \
        || echo "[FAIL] $TAG -- see $LOG"
    done
  done
done
echo "done -> python3 experiments/summarize.py"
