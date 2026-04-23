#!/usr/bin/env bash
# alexnet_table_sweep.sh

OUTDIR="alexnet_sweep_results"
mkdir -p "$OUTDIR"
RESULTS_CSV="alexnet_sweep_summary.csv"

# Write CSV header
echo "table_size,real_time,user_time,sys_time,cpu_total" > "$RESULTS_CSV"

echo "Starting AlexNet Table Size Sweep..."
echo "Sizes: 200 to 3000, Step: 200"

for TSIZE in $(seq 200 200 3000); do
    echo "----------------------------------------------------"
    echo "Running with Q-Table Size: $TSIZE"
    
    LOGFILE="$OUTDIR/alexnet_t${TSIZE}.log"
    
    # We MUST run from src/GAMMA so maestro can be found
    pushd src/GAMMA > /dev/null
    
    /usr/bin/time -f "REAL_TIME_S=%e USER_TIME_S=%U SYS_TIME_S=%S" \
        python3 main.py \
            --model alexnet \
            --epochs 50 \
            --num_pop 200 \
            --num_pe 256 \
            --seed 42 \
            --use_qfilter \
            --auto_threshold \
            --q_table_size "$TSIZE" \
            --epsilon_decay 0.9 \
            --outdir "../../$OUTDIR/run_t${TSIZE}" > "../../$LOGFILE" 2>&1
            
    popd > /dev/null
            
    # Extract times from log
    # Note: time output is usually at the end of the log
    REAL=$(tail -n 1 "$LOGFILE" | grep "REAL_TIME_S=" | sed 's/.*REAL_TIME_S=\([0-9.]*\).*/\1/')
    USER=$(tail -n 1 "$LOGFILE" | grep "USER_TIME_S=" | sed 's/.*USER_TIME_S=\([0-9.]*\).*/\1/')
    SYS=$(tail -n 1 "$LOGFILE" | grep "SYS_TIME_S=" | sed 's/.*SYS_TIME_S=\([0-9.]*\).*/\1/')
    
    # If extraction failed, maybe it's not the last line
    if [ -z "$REAL" ]; then
        REAL=$(grep "REAL_TIME_S=" "$LOGFILE" | tail -n 1 | sed 's/.*REAL_TIME_S=\([0-9.]*\).*/\1/')
        USER=$(grep "USER_TIME_S=" "$LOGFILE" | tail -n 1 | sed 's/.*USER_TIME_S=\([0-9.]*\).*/\1/')
        SYS=$(grep "SYS_TIME_S=" "$LOGFILE" | tail -n 1 | sed 's/.*SYS_TIME_S=\([0-9.]*\).*/\1/')
    fi

    # Calculate CPU Total (User + Sys)
    if [ -n "$USER" ] && [ -n "$SYS" ]; then
        if command -v bc > /dev/null; then
            CPU_TOTAL=$(echo "$USER + $SYS" | bc)
        else
            CPU_TOTAL=$(python3 -c "print($USER + $SYS)")
        fi
    else
        CPU_TOTAL="ERROR"
    fi
    
    echo "Completed $TSIZE: CPU Total = ${CPU_TOTAL}s (Real: ${REAL}s)"
    echo "$TSIZE,$REAL,$USER,$SYS,$CPU_TOTAL" >> "$RESULTS_CSV"
done

echo "----------------------------------------------------"
echo "Sweep Complete. Results saved in $RESULTS_CSV"
