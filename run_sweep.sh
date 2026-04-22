#!/usr/bin/env bash
# =============================================================================
# run_sweep.sh  — GAMMA Q-Filter Ablation Sweep
# =============================================================================
# Runs GAMMA across all 18 models in 3 modes:
#   1. Baseline          (no Q-filter)
#   2. Q-Filter          (with Q-filter, no guided mutation)
#   3. Q-Filter + Guided (with Q-filter + guided mutation points)
#
# Sweep axes:
#   - Q-table sizes : 500, 1000, 5000, 10000
#   - Epsilon decay : 0.70, 0.80, 0.90
#
# Timing: /usr/bin/time captures real / user / sys for every run
# Output: results/<model>_<tag>/run.log  +  result_c.csv inside subdirectory
# =============================================================================

cd "$(dirname "$0")/src/GAMMA"
OUTROOT="../../results"

MODELS="resnet18 resnet50 vgg16 alexnet googlenet densenet squeezenet \
        wide_resnet50 resnext50_32x4d shufflenet_v2 mobilenet_v2 mnasnet \
        BERT_m ALBERT_m T5_m transformer dlrmRMC1_m ncf_m"
TABLE_SIZES="500 1000 5000 10000"
EPSILONS="0.70 0.80 0.90"

# Paper parameters
POP=200
GEN=50
NUM_PE=256
L1=512
L2=108000

mkdir -p "$OUTROOT"

# run_exp MODEL USE_QF TSIZE EPS GUIDED
run_exp() {
    local MODEL=$1
    local USE_QF=$2
    local TSIZE=$3
    local EPS=$4
    local GUIDED=$5

    if [ "$USE_QF" = "1" ]; then
        if [ "$GUIDED" = "1" ]; then
            TAG="qfilter_guided_t${TSIZE}_e${EPS}"
        else
            TAG="qfilter_t${TSIZE}_e${EPS}"
        fi
    else
        TAG="baseline"
    fi

    local OUTDIR="$OUTROOT/${MODEL}_${TAG}"
    mkdir -p "$OUTDIR"
    local LOGFILE="$OUTDIR/run.log"

    # Skip if already completed successfully
    if grep -q "REAL_TIME_S=" "$LOGFILE" 2>/dev/null; then
        echo "[SKIP]  $MODEL | $TAG  (already done)"
        return 0
    fi

    echo "[SWEEP] $MODEL | $TAG  →  $OUTDIR"

    local CMD="python main.py \
        --model $MODEL \
        --num_pop $POP \
        --epochs $GEN \
        --num_pe $NUM_PE \
        --l1_size $L1 \
        --l2_size $L2 \
        --seed 42 \
        --outdir results/${MODEL}_${TAG}"

    if [ "$USE_QF" = "1" ]; then
        CMD="$CMD --use_qfilter --q_table_size $TSIZE --epsilon_decay $EPS"
        if [ "$GUIDED" = "1" ]; then
            CMD="$CMD --q_guided_mutation"
        fi
    fi

    # /usr/bin/time writes real/user/sys to stderr → captured into LOGFILE via 2>&1
    /usr/bin/time -f "REAL_TIME_S=%e USER_TIME_S=%U SYS_TIME_S=%S" \
        bash -c "$CMD" > "$LOGFILE" 2>&1 && echo "[SWEEP] Done: $MODEL | $TAG" \
        || echo "[ERROR] $MODEL | $TAG — check $LOGFILE"
}

# --- 1. Baseline (no Q-filter) ---
echo "===== PHASE 1: Baseline ====="
for MODEL in $MODELS; do
    run_exp "$MODEL" "0" "0" "0" "0"
done

# --- 2. Q-Filter (no guided mutation) ---
echo "===== PHASE 2: Q-Filter ====="
for MODEL in $MODELS; do
    for TSIZE in $TABLE_SIZES; do
        for EPS in $EPSILONS; do
            run_exp "$MODEL" "1" "$TSIZE" "$EPS" "0"
        done
    done
done

# --- 3. Q-Filter + Guided Mutation ---
echo "===== PHASE 3: Q-Filter + Guided Mutation ====="
for MODEL in $MODELS; do
    for TSIZE in $TABLE_SIZES; do
        for EPS in $EPSILONS; do
            run_exp "$MODEL" "1" "$TSIZE" "$EPS" "1"
        done
    done
done

echo ""
echo "=== All experiments done. Results in $OUTROOT ==="
