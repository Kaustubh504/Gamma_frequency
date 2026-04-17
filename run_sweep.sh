#!/usr/bin/env bash
# =============================================================================
# run_sweep.sh  — GAMMA Q-Filter Ablation Sweep
# =============================================================================
# Runs GAMMA (with & without Q-filter) across:
#   - Models      : resnet18, vgg16, mobilenet_v2, mnasnet
#   - Q-table sizes: 500, 1000, 5000, 10000
#   - Epsilon values: 0.70, 0.80, 0.90 (epsilon_decay)
# Epochs / population match the paper: pop=200, gen=50
#
# Usage:  bash run_sweep.sh
# Output: results/<exp>/result_c.csv  (one per experiment)
# =============================================================================

set -e
cd "$(dirname "$0")/src/GAMMA"

MODELS="resnet18 vgg16 mobilenet_v2 mnasnet"
TABLE_SIZES="500 1000 5000 10000"
EPSILONS="0.70 0.80 0.90"

# Paper parameters
POP=200
GEN=50
NUM_PE=256
L1=512
L2=108000

OUTROOT="../../results"
mkdir -p "$OUTROOT"

run_exp() {
    local MODEL=$1
    local USE_QF=$2
    local TSIZE=$3
    local EPS=$4

    if [ "$USE_QF" = "1" ]; then
        TAG="qfilter_t${TSIZE}_e${EPS}"
    else
        TAG="baseline"
    fi

    local OUTDIR="$OUTROOT/${MODEL}_${TAG}"
    mkdir -p "$OUTDIR"
    local LOGFILE="$OUTDIR/run.log"

    echo "[SWEEP] $MODEL | $TAG  →  $OUTDIR"

    local CMD="python main.py \
        --model $MODEL \
        --num_pop $POP \
        --epochs $GEN \
        --num_pe $NUM_PE \
        --l1_size $L1 \
        --l2_size $L2 \
        --outdir results/${MODEL}_${TAG}"

    if [ "$USE_QF" = "1" ]; then
        CMD="$CMD --use_qfilter --q_table_size $TSIZE --epsilon_decay $EPS"
    fi

    # Time the run; capture wall-clock seconds
    START=$(date +%s%N)
    eval "$CMD" > "$LOGFILE" 2>&1
    END=$(date +%s%N)
    ELAPSED=$(( (END - START) / 1000000 ))   # milliseconds → keep as ms, convert later

    # Append timing to log
    echo "WALL_TIME_MS=$ELAPSED" >> "$LOGFILE"
    echo "[SWEEP] Done: $MODEL | $TAG  (${ELAPSED}ms)"
}

# --- Baseline (no Q-filter) for each model ---
for MODEL in $MODELS; do
    run_exp "$MODEL" "0" "0" "0"
done

# --- Q-Filter sweep ---
for MODEL in $MODELS; do
    for TSIZE in $TABLE_SIZES; do
        for EPS in $EPSILONS; do
            run_exp "$MODEL" "1" "$TSIZE" "$EPS"
        done
    done
done

echo ""
echo "=== All experiments done. Results in $OUTROOT ==="
