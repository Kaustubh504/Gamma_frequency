#!/usr/bin/env python3
"""
benchmark_sweep.py
==================
Automated Q-Learning hyperparameter sweep & benchmarking for GAMMA.

For each model in data/model/:
  1. Sweep q_table_size × epsilon_decay × q_alpha  (with --use_qfilter)
  2. Run baseline (no Q-filter)
  3. Generate per-model Excel with sheets:
     - Hyperparameter Sweep
     - Baseline vs Q-Filter (optimal)
     - Per-Generation Stats (optimal Q-filter run)

Usage:
  # Full sweep (all models, default grid)
  python3 benchmark_sweep.py

  # Single model, small grid (quick test)
  python3 benchmark_sweep.py --models resnet18 --table-sizes 5000 --decays 0.98 --alphas 0.5

  # Dry run (print commands only)
  python3 benchmark_sweep.py --dry-run

  # Skip sweep, just regenerate Excel from existing output dirs
  python3 benchmark_sweep.py --parse-only
"""

import argparse
import csv
import glob
import os
import re
import resource
import subprocess
import sys
import time
from datetime import datetime
from itertools import product

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
GAMMA_DIR = os.path.join(PROJECT_ROOT, "src", "GAMMA")
MODEL_DIR = os.path.join(PROJECT_ROOT, "data", "model")
PYTHON = os.path.join(PROJECT_ROOT, "venv", "bin", "python3")
if not os.path.exists(PYTHON):
    PYTHON = "python3"

RESULTS_DIR = os.path.join(PROJECT_ROOT, "benchmark_results")

# Fixed experiment params (per paper)
EPOCHS = 50
NUM_POP = 200
NUM_PE = 168
L1_SIZE = 512
L2_SIZE = 108000
NOC_BW = 81920000
NUM_LAYER = 1
FITNESS1 = "latency"
FITNESS2 = "power"
Q_GAMMA = 0.9  # discount factor, fixed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def discover_models(model_dir, exclude=None):
    """Auto-discover all model CSV files."""
    exclude = exclude or {"example", "try", "manual"}
    models = []
    for f in sorted(os.listdir(model_dir)):
        if f.endswith(".csv"):
            name = f.replace(".csv", "")
            if name not in exclude:
                models.append(name)
    return models


def build_base_args():
    """Common CLI args for main.py."""
    return [
        "--fitness1", FITNESS1,
        "--fitness2", FITNESS2,
        "--num_pe", str(NUM_PE),
        "--l1_size", str(L1_SIZE),
        "--l2_size", str(L2_SIZE),
        "--NocBW", str(NOC_BW),
        "--epochs", str(EPOCHS),
        "--num_pop", str(NUM_POP),
        "--num_layer", str(NUM_LAYER),
    ]


def run_experiment(model, outdir_name, use_qfilter=False,
                   q_table_size=None, q_alpha=None, epsilon_decay=None,
                   dry_run=False):
    """
    Run a single GAMMA experiment. Returns dict of metrics.
    """
    args = [PYTHON, "main.py"] + build_base_args()
    args += ["--model", model, "--outdir", outdir_name]

    if use_qfilter:
        args += ["--use_qfilter"]
        if q_table_size is not None:
            args += ["--q_table_size", str(q_table_size)]
        if q_alpha is not None:
            args += ["--q_alpha", str(q_alpha)]
        args += ["--q_gamma", str(Q_GAMMA)]
        if epsilon_decay is not None:
            args += ["--epsilon_decay", str(epsilon_decay)]

    cmd_str = " ".join(args)
    if dry_run:
        print(f"  [DRY-RUN] {cmd_str}")
        return {"status": "dry-run"}

    print(f"  → Running: {cmd_str}")
    wall_start = time.time()
    # Capture child CPU time via resource module (cumulative user + sys)
    children_before = resource.getrusage(resource.RUSAGE_CHILDREN)

    result = subprocess.run(
        args, cwd=GAMMA_DIR,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, timeout=3600  # 1 hour max per run
    )

    wall_time = time.time() - wall_start
    children_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    user_time = children_after.ru_utime - children_before.ru_utime
    sys_time = children_after.ru_stime - children_before.ru_stime
    cpu_time = user_time + sys_time
    stdout = result.stdout or ""

    # Print timing like bash `time` command
    minutes, secs = divmod(wall_time, 60)
    print(f"  ⏱  real\t{int(minutes)}m{secs:.3f}s")
    print(f"     user\t{user_time:.3f}s")
    print(f"     sys\t{sys_time:.3f}s")

    # Save log with timing header for later --parse-only recovery
    log_dir = os.path.join(RESULTS_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"{outdir_name}.log")
    timing_header = (f"## TIMING: wall_time={wall_time:.2f} "
                     f"cpu_time={cpu_time:.2f} "
                     f"user_time={user_time:.2f} "
                     f"sys_time={sys_time:.2f}\n")
    with open(log_path, "w") as f:
        f.write(timing_header)
        f.write(stdout)

    metrics = parse_output(stdout, model, outdir_name, wall_time, cpu_time,
                           use_qfilter, q_table_size, q_alpha, epsilon_decay)
    metrics["user_time_sec"] = round(user_time, 2)
    metrics["sys_time_sec"] = round(sys_time, 2)
    metrics["returncode"] = result.returncode
    return metrics


def parse_output(stdout, model, outdir_name, wall_time, cpu_time,
                 use_qfilter, q_table_size, q_alpha, epsilon_decay):
    """Parse stdout and result_c.csv to extract all metrics."""
    metrics = {
        "model": model,
        "outdir": outdir_name,
        "use_qfilter": use_qfilter,
        "q_table_size": q_table_size if use_qfilter else "N/A",
        "q_alpha": q_alpha if use_qfilter else "N/A",
        "q_gamma": Q_GAMMA if use_qfilter else "N/A",
        "epsilon_decay": epsilon_decay if use_qfilter else "N/A",
        "epochs": EPOCHS,
        "num_pop": NUM_POP,
        "wall_time_sec": round(wall_time, 2),
        "cpu_time_sec": round(cpu_time, 2),
        # Defaults
        "best_reward": None,
        "best_runtime_cycles": None,
        "best_area_mm2": None,
        "pe_area_ratio_pct": None,
        "num_pe": None,
        "l1_buffer": None,
        "l2_buffer": None,
        "total_maestro_calls": None,
        "total_skipped": None,
        "skip_pct": None,
        "final_epsilon": None,
        "q_states_eval": None,
        "q_states_cross": None,
        "q_states_growth": None,
        "q_states_aging": None,
        "status": "ok",
    }

    # Parse final result line: "Reward: ..., Runtime: ..., Area: ..."
    reward_m = re.search(r"Reward:\s*([-\d.eE+]+),\s*Runtime:\s*([\d.]+)\(cycles\),\s*Area:\s*([\d.]+)\(mm2\),\s*PE Area_ratio:\s*([\d.]+)%.*?Num_PE:\s*([\d.]+).*?L1 Buffer:\s*([\d.]+).*?L2 Buffer:\s*([\d.]+)", stdout)
    if reward_m:
        metrics["best_reward"] = float(reward_m.group(1))
        metrics["best_runtime_cycles"] = float(reward_m.group(2))
        metrics["best_area_mm2"] = float(reward_m.group(3))
        metrics["pe_area_ratio_pct"] = float(reward_m.group(4))
        metrics["num_pe"] = float(reward_m.group(5))
        metrics["l1_buffer"] = float(reward_m.group(6))
        metrics["l2_buffer"] = float(reward_m.group(7))

    # Parse Q-filter summary
    if use_qfilter:
        m = re.search(r"Total MAESTRO calls\s*:\s*(\d+)", stdout)
        if m:
            metrics["total_maestro_calls"] = int(m.group(1))
        m = re.search(r"Total skipped by Q-filter\s*:\s*(\d+)\s*\(([\d.]+)%\)", stdout)
        if m:
            metrics["total_skipped"] = int(m.group(1))
            metrics["skip_pct"] = float(m.group(2))
        m = re.search(r"Final ε\s*:\s*([\d.]+)", stdout)
        if m:
            metrics["final_epsilon"] = float(m.group(1))
        m = re.search(r"Eval States Known\s*:\s*(\d+)", stdout)
        if m:
            metrics["q_states_eval"] = int(m.group(1))
        m = re.search(r"Crossover States Known\s*:\s*(\d+)", stdout)
        if m:
            metrics["q_states_cross"] = int(m.group(1))
        m = re.search(r"Growth States Known\s*:\s*(\d+)", stdout)
        if m:
            metrics["q_states_growth"] = int(m.group(1))
        m = re.search(r"Aging States Known\s*:\s*(\d+)", stdout)
        if m:
            metrics["q_states_aging"] = int(m.group(1))

        # Per-generation stats
        gen_stats = []
        for gm in re.finditer(
            r"\[QFilter\] Gen (\d+): evaluated=(\d+), skipped=(\d+), ε=([\d.]+), Eval Q-states=(\d+)",
            stdout
        ):
            gen_stats.append({
                "gen": int(gm.group(1)),
                "evaluated": int(gm.group(2)),
                "skipped": int(gm.group(3)),
                "epsilon": float(gm.group(4)),
                "q_states": int(gm.group(5)),
            })
        metrics["gen_stats"] = gen_stats
    else:
        # Baseline: all evaluated, none skipped
        total_candidates = EPOCHS * (NUM_POP + 10)  # approx (pop + elite)
        metrics["total_maestro_calls"] = total_candidates
        metrics["total_skipped"] = 0
        metrics["skip_pct"] = 0.0
        metrics["gen_stats"] = []

    return metrics


def parse_existing_log(log_path, model, outdir_name, use_qfilter,
                       q_table_size=None, q_alpha=None, epsilon_decay=None):
    """Parse a previously saved log file, recovering timing from header."""
    with open(log_path, "r") as f:
        content = f.read()
    # Try to extract saved timing from header
    wall_time = 0.0
    cpu_time = 0.0
    user_time = 0.0
    sys_time = 0.0
    timing_m = re.search(
        r"## TIMING: wall_time=([\d.]+) cpu_time=([\d.]+)"
        r"(?: user_time=([\d.]+) sys_time=([\d.]+))?",
        content)
    if timing_m:
        wall_time = float(timing_m.group(1))
        cpu_time = float(timing_m.group(2))
        if timing_m.group(3):
            user_time = float(timing_m.group(3))
            sys_time = float(timing_m.group(4))
    metrics = parse_output(content, model, outdir_name, wall_time, cpu_time,
                           use_qfilter, q_table_size, q_alpha, epsilon_decay)
    metrics["user_time_sec"] = round(user_time, 2)
    metrics["sys_time_sec"] = round(sys_time, 2)
    return metrics


def find_optimal(sweep_results):
    """Find the optimal hyperparameter combo from sweep results.
    Optimal = best (highest) reward; tie-break by lowest wall_time."""
    valid = [r for r in sweep_results
             if r.get("best_reward") is not None and r.get("status") == "ok"]
    if not valid:
        return None
    # Higher reward is better (reward is negative, so max is best)
    return max(valid, key=lambda r: (r["best_reward"], -r["wall_time_sec"]))


def generate_excel(model, sweep_results, baseline_metrics, optimal_metrics,
                   output_dir):
    """Generate an Excel file for one model with 3 sheets."""
    try:
        import pandas as pd
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils.dataframe import dataframe_to_rows
    except ImportError:
        print("  ⚠ openpyxl/pandas not available, skipping Excel generation")
        return

    os.makedirs(output_dir, exist_ok=True)
    xlsx_path = os.path.join(output_dir, f"results_{model}.xlsx")

    wb = Workbook()

    # ── Styles ──
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    def style_header(ws, num_cols):
        for col in range(1, num_cols + 1):
            cell = ws.cell(row=1, column=col)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
            cell.border = thin_border

    # ── Sheet 1: Hyperparameter Sweep ──
    ws1 = wb.active
    ws1.title = "Hyperparameter Sweep"
    sweep_cols = [
        "q_table_size", "epsilon_decay", "q_alpha",
        "best_reward", "best_runtime_cycles",
        "wall_time_sec", "cpu_time_sec", "user_time_sec", "sys_time_sec",
        "total_maestro_calls", "total_skipped", "skip_pct",
        "final_epsilon", "q_states_eval",
        "best_area_mm2", "pe_area_ratio_pct", "l1_buffer", "l2_buffer"
    ]
    ws1.append(sweep_cols)
    for r in sweep_results:
        row = [r.get(c, "") for c in sweep_cols]
        ws1.append(row)
    style_header(ws1, len(sweep_cols))
    for col in ws1.columns:
        ws1.column_dimensions[col[0].column_letter].width = 18

    # ── Sheet 2: Baseline vs Q-Filter ──
    ws2 = wb.create_sheet("Baseline vs Q-Filter")
    comparison_metrics = [
        ("Best Reward", "best_reward"),
        ("Runtime (Cycles)", "best_runtime_cycles"),
        ("Wall Time / real (sec)", "wall_time_sec"),
        ("CPU Time / user+sys (sec)", "cpu_time_sec"),
        ("User Time (sec)", "user_time_sec"),
        ("Sys Time (sec)", "sys_time_sec"),
        ("Total MAESTRO Calls", "total_maestro_calls"),
        ("Total Skipped", "total_skipped"),
        ("Skip %", "skip_pct"),
        ("Area (mm²)", "best_area_mm2"),
        ("PE Area Ratio %", "pe_area_ratio_pct"),
        ("L1 Buffer", "l1_buffer"),
        ("L2 Buffer", "l2_buffer"),
        ("Final Epsilon", "final_epsilon"),
        ("Q-States (Eval)", "q_states_eval"),
        ("Optimal Alpha", "q_alpha"),
        ("Optimal Epsilon Decay", "epsilon_decay"),
        ("Optimal Q-Table Size", "q_table_size"),
    ]
    ws2.append(["Metric", "Baseline", "Q-Filter (Optimal)", "Improvement %"])
    for label, key in comparison_metrics:
        bval = baseline_metrics.get(key) if baseline_metrics else "N/A"
        qval = optimal_metrics.get(key) if optimal_metrics else "N/A"
        # Calculate improvement for numeric values
        imp = ""
        if isinstance(bval, (int, float)) and isinstance(qval, (int, float)):
            if bval != 0 and bval is not None:
                if key in ("best_reward",):
                    # Higher is better
                    imp = f"{((qval - bval) / abs(bval)) * 100:.1f}%"
                elif key in ("wall_time_sec", "cpu_time_sec",
                             "user_time_sec", "sys_time_sec",
                             "best_runtime_cycles", "total_maestro_calls"):
                    # Lower is better
                    imp = f"{((bval - qval) / abs(bval)) * 100:.1f}%"
        ws2.append([label,
                    bval if bval is not None else "N/A",
                    qval if qval is not None else "N/A",
                    imp])
    style_header(ws2, 4)
    for col_letter in ['A', 'B', 'C', 'D']:
        ws2.column_dimensions[col_letter].width = 25

    # ── Sheet 3: Per-Generation Stats ──
    ws3 = wb.create_sheet("Per-Gen Stats (Q-Filter)")
    gen_stats = optimal_metrics.get("gen_stats", []) if optimal_metrics else []
    ws3.append(["Generation", "Evaluated", "Skipped", "Epsilon", "Q-States"])
    for gs in gen_stats:
        ws3.append([gs["gen"], gs["evaluated"], gs["skipped"],
                    gs["epsilon"], gs["q_states"]])
    style_header(ws3, 5)
    for col in ws3.columns:
        ws3.column_dimensions[col[0].column_letter].width = 15

    # Apply borders to all data cells
    for ws in [ws1, ws2, ws3]:
        for row in ws.iter_rows(min_row=1, max_row=ws.max_row,
                                max_col=ws.max_column):
            for cell in row:
                cell.border = thin_border

    wb.save(xlsx_path)
    print(f"  ✅ Saved: {xlsx_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="GAMMA Q-Learning Benchmark Sweep"
    )
    parser.add_argument("--models", nargs="+", default=None,
                        help="Models to benchmark (default: all in data/model/)")
    parser.add_argument("--table-sizes", nargs="+", type=int,
                        default=[1000, 5000, 10000],
                        help="Q-table sizes to sweep")
    parser.add_argument("--decays", nargs="+", type=float,
                        default=[0.85, 0.90, 0.95, 0.98],
                        help="Epsilon decay values to sweep")
    parser.add_argument("--alphas", nargs="+", type=float,
                        default=[0.1, 0.3, 0.5],
                        help="Q-alpha values to sweep")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print commands without running")
    parser.add_argument("--parse-only", action="store_true",
                        help="Skip runs, parse existing logs & generate Excel")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip runs whose output directory already exists")
    parser.add_argument("--exclude-models", nargs="+",
                        default=["example", "try", "manual"],
                        help="Models to exclude")
    args = parser.parse_args()

    # Discover models
    if args.models:
        models = args.models
    else:
        models = discover_models(MODEL_DIR, set(args.exclude_models))

    os.makedirs(RESULTS_DIR, exist_ok=True)

    grid = list(product(args.table_sizes, args.decays, args.alphas))
    total_runs = len(models) * (len(grid) + 1)  # +1 for baseline per model

    print("=" * 70)
    print(f"🚀 GAMMA Q-Learning Benchmark Sweep")
    print(f"   Models: {len(models)} → {', '.join(models)}")
    print(f"   Sweep grid: {len(grid)} combos "
          f"(table_sizes={args.table_sizes} × decays={args.decays} "
          f"× alphas={args.alphas})")
    print(f"   Total experiments: {total_runs} "
          f"({len(grid)} sweep + 1 baseline per model)")
    print(f"   Epochs: {EPOCHS}  |  Population: {NUM_POP}")
    print(f"   Output: {RESULTS_DIR}")
    print("=" * 70)

    all_model_results = {}

    for mi, model in enumerate(models):
        print(f"\n{'='*70}")
        print(f"📊 [{mi+1}/{len(models)}] MODEL: {model}")
        print(f"{'='*70}")

        sweep_results = []
        baseline_metrics = None

        # ── Phase 1: Hyperparameter Sweep ──
        print(f"\n  ── Phase 1: Hyperparameter Sweep ({len(grid)} combos) ──")
        for gi, (ts, decay, alpha) in enumerate(grid):
            outdir_name = f"sweep_{model}_ts{ts}_d{decay}_a{alpha}"
            log_path = os.path.join(RESULTS_DIR, "logs", f"{outdir_name}.log")

            print(f"\n  [{gi+1}/{len(grid)}] "
                  f"table_size={ts}, decay={decay}, alpha={alpha}")

            if args.parse_only and os.path.exists(log_path):
                print(f"    → Parsing existing log: {log_path}")
                m = parse_existing_log(log_path, model, outdir_name, True,
                                       ts, alpha, decay)
                sweep_results.append(m)
                continue

            outdir_full = os.path.join(PROJECT_ROOT, outdir_name)
            if args.skip_existing and os.path.exists(outdir_full):
                print(f"    → Skipping (output dir exists)")
                if os.path.exists(log_path):
                    m = parse_existing_log(log_path, model, outdir_name, True,
                                           ts, alpha, decay)
                    sweep_results.append(m)
                continue

            m = run_experiment(
                model, outdir_name, use_qfilter=True,
                q_table_size=ts, q_alpha=alpha, epsilon_decay=decay,
                dry_run=args.dry_run
            )
            sweep_results.append(m)

        # ── Phase 2: Baseline ──
        print(f"\n  ── Phase 2: Baseline (no Q-filter) ──")
        baseline_outdir = f"sweep_{model}_baseline"
        baseline_log = os.path.join(RESULTS_DIR, "logs",
                                    f"{baseline_outdir}.log")

        if args.parse_only and os.path.exists(baseline_log):
            print(f"    → Parsing existing log")
            baseline_metrics = parse_existing_log(
                baseline_log, model, baseline_outdir, False)
        elif args.skip_existing and os.path.exists(
                os.path.join(PROJECT_ROOT, baseline_outdir)):
            print(f"    → Skipping (exists)")
            if os.path.exists(baseline_log):
                baseline_metrics = parse_existing_log(
                    baseline_log, model, baseline_outdir, False)
        else:
            baseline_metrics = run_experiment(
                model, baseline_outdir, use_qfilter=False,
                dry_run=args.dry_run
            )

        # ── Phase 3: Find Optimal & Generate Excel ──
        optimal = find_optimal(sweep_results)
        if optimal:
            print(f"\n  🏆 Optimal for {model}: "
                  f"table_size={optimal.get('q_table_size')}, "
                  f"decay={optimal.get('epsilon_decay')}, "
                  f"alpha={optimal.get('q_alpha')}, "
                  f"reward={optimal.get('best_reward')}, "
                  f"skip%={optimal.get('skip_pct')}")

        if not args.dry_run:
            generate_excel(model, sweep_results, baseline_metrics, optimal,
                           RESULTS_DIR)

        all_model_results[model] = {
            "sweep": sweep_results,
            "baseline": baseline_metrics,
            "optimal": optimal,
        }

    # ── Summary across all models ──
    if not args.dry_run:
        print(f"\n{'='*70}")
        print(f"🎉 ALL BENCHMARKS COMPLETE!")
        print(f"{'='*70}")
        print(f"\n📁 Excel files saved to: {RESULTS_DIR}/")
        for model, data in all_model_results.items():
            opt = data.get("optimal")
            bl = data.get("baseline")
            if opt and bl and bl.get("best_reward"):
                print(f"  {model:20s}  "
                      f"Baseline reward={bl.get('best_reward')}, "
                      f"Q-filter reward={opt.get('best_reward')}, "
                      f"skip%={opt.get('skip_pct')}")
            elif opt:
                print(f"  {model:20s}  "
                      f"Q-filter reward={opt.get('best_reward')}, "
                      f"skip%={opt.get('skip_pct')}")
        generate_summary_excel(all_model_results, RESULTS_DIR)


def generate_summary_excel(all_results, output_dir):
    """Generate a combined summary Excel across all models."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        return

    wb = Workbook()
    ws = wb.active
    ws.title = "All Models Summary"

    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="2F5496", end_color="2F5496",
                              fill_type="solid")
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    headers = [
        "Model",
        "Baseline Reward", "Baseline Runtime", "Baseline Wall Time",
        "Baseline CPU Time",
        "QFilter Reward", "QFilter Runtime", "QFilter Wall Time",
        "QFilter CPU Time",
        "Optimal Alpha", "Optimal Decay", "Optimal Table Size",
        "Total Skipped", "Skip %",
        "Reward Improvement %", "Time Savings %"
    ]
    ws.append(headers)
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
        cell.border = thin_border

    for model, data in all_results.items():
        bl = data.get("baseline") or {}
        opt = data.get("optimal") or {}

        bl_reward = bl.get("best_reward")
        opt_reward = opt.get("best_reward")

        reward_imp = ""
        if bl_reward and opt_reward and bl_reward != 0:
            reward_imp = f"{((opt_reward - bl_reward) / abs(bl_reward)) * 100:.1f}%"

        time_save = ""
        bl_wt = bl.get("wall_time_sec")
        opt_wt = opt.get("wall_time_sec")
        if bl_wt and opt_wt and bl_wt != 0:
            time_save = f"{((bl_wt - opt_wt) / abs(bl_wt)) * 100:.1f}%"

        ws.append([
            model,
            bl_reward, bl.get("best_runtime_cycles"), bl_wt,
            bl.get("cpu_time_sec"),
            opt_reward, opt.get("best_runtime_cycles"), opt_wt,
            opt.get("cpu_time_sec"),
            opt.get("q_alpha", ""), opt.get("epsilon_decay", ""),
            opt.get("q_table_size", ""),
            opt.get("total_skipped", ""), opt.get("skip_pct", ""),
            reward_imp, time_save
        ])

    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 18

    for row in ws.iter_rows(min_row=1, max_row=ws.max_row,
                            max_col=ws.max_column):
        for cell in row:
            cell.border = thin_border

    path = os.path.join(output_dir, "summary_all_models.xlsx")
    wb.save(path)
    print(f"\n  ✅ Combined summary: {path}")


if __name__ == "__main__":
    main()
