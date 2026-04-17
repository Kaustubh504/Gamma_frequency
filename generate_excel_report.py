"""
generate_excel_report.py
========================
Reads GAMMA sweep results from results/ directory and produces a
formatted Excel workbook with:
  Sheet 1 – Raw Results         (all experiments, all metrics)
  Sheet 2 – Baseline vs Q-Filter Summary (per model)
  Sheet 3 – Q-Table Size Effect  (latency, cpu-time, reward vs table size)
  Sheet 4 – Epsilon Effect        (same metrics vs epsilon_decay)
  Sheet 5 – Q-Table Field Guide   (description of every Q-table field)

Run after run_sweep.sh completes:
    python generate_excel_report.py --results_dir ./Gamma_frequency/results
"""

import os
import re
import glob
import argparse
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import (Font, PatternFill, Alignment,
                              Border, Side, numbers)
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.series import DataPoint
from datetime import datetime

# ── Colour palette ────────────────────────────────────────────────────────────
HDR_FILL   = PatternFill("solid", start_color="1F4E79")   # dark blue
SUB_FILL   = PatternFill("solid", start_color="2E75B6")   # medium blue
BAND_FILL  = PatternFill("solid", start_color="D9E1F2")   # light blue
GREEN_FILL = PatternFill("solid", start_color="E2EFDA")   # light green
YELL_FILL  = PatternFill("solid", start_color="FFF2CC")   # yellow
HDR_FONT   = Font(name="Arial", bold=True, color="FFFFFF", size=10)
BODY_FONT  = Font(name="Arial", size=9)
BOLD_FONT  = Font(name="Arial", bold=True, size=9)
thin       = Side(style="thin", color="BFBFBF")
MED        = Side(style="medium", color="595959")
BORDER     = Border(left=thin, right=thin, top=thin, bottom=thin)
MED_BORDER = Border(left=MED,  right=MED,  top=MED,  bottom=MED)
CENTER     = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT       = Alignment(horizontal="left",   vertical="center", wrap_text=True)

def hdr(ws, row, col, value, fill=HDR_FILL, font=HDR_FONT, align=CENTER, border=BORDER):
    c = ws.cell(row=row, column=col, value=value)
    c.fill = fill; c.font = font; c.alignment = align; c.border = border
    return c

def cell(ws, row, col, value, fill=None, font=BODY_FONT, align=CENTER, border=BORDER, fmt=None):
    c = ws.cell(row=row, column=col, value=value)
    if fill: c.fill = fill
    c.font = font; c.alignment = align; c.border = border
    if fmt: c.number_format = fmt
    return c

def set_col_widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

# ── Result parsing ─────────────────────────────────────────────────────────────
def parse_result_dir(path):
    """
    Parses a single experiment result directory.
    Returns a dict of metrics, or None if incomplete.
    """
    folder = os.path.basename(path)
    # Detect baseline vs qfilter
    is_qf = "qfilter" in folder
    parts = folder.split("_")
    model = parts[0]

    table_size, epsilon = None, None
    if is_qf:
        # format: <model>_qfilter_t<size>_e<eps>
        for p in parts:
            if p.startswith("t") and p[1:].isdigit():
                table_size = int(p[1:])
            if p.startswith("e") and re.match(r"e[\d.]+", p):
                epsilon = float(p[1:])

    # Try to parse result CSV (one file per layer, last one = last layer result)
    csv_files = glob.glob(os.path.join(path, "**", "result_c.csv"), recursive=True)
    csv_files += glob.glob(os.path.join(path, "result_c.csv"))

    best_runtime, best_energy, best_reward = None, None, None
    if csv_files:
        try:
            df = pd.read_csv(csv_files[0])
            if "runtime" in df.columns:
                best_runtime = float(df["runtime"].iloc[-1])
            if "energy" in df.columns:
                best_energy = float(df["energy"].iloc[-1]) if "energy" in df.columns else None
        except Exception:
            pass

    # Parse log for wall time and Q-filter stats
    log_file = os.path.join(path, "run.log")
    wall_ms, total_eval, total_skip, final_eps, q_states = None, None, None, None, None
    best_reward_log = None
    if os.path.exists(log_file):
        with open(log_file) as f:
            text = f.read()
        m = re.search(r"WALL_TIME_MS=(\d+)", text)
        if m: wall_ms = int(m.group(1))
        m = re.search(r"Total MAESTRO calls\s*:\s*(\d+)", text)
        if m: total_eval = int(m.group(1))
        m = re.search(r"Total skipped by Q-filter\s*:\s*(\d+)", text)
        if m: total_skip = int(m.group(1))
        m = re.search(r"Final ε\s*:\s*([0-9.]+)", text)
        if m: final_eps = float(m.group(1))
        m = re.search(r"Eval States Known\s*:\s*(\d+)", text)
        if m: q_states = int(m.group(1))
        # Best reward from "Reward: X.XXe+YY"
        rewards = re.findall(r"Reward:\s*([-\d.e+]+)", text)
        if rewards:
            try: best_reward_log = float(rewards[-1])
            except: pass

    return {
        "model":        model,
        "mode":         "Q-Filter" if is_qf else "Baseline",
        "q_table_size": table_size,
        "epsilon_decay":epsilon,
        "best_runtime_cycles": best_runtime,
        "best_reward":   best_reward_log,
        "wall_time_ms":  wall_ms,
        "wall_time_s":   round(wall_ms/1000, 2) if wall_ms else None,
        "maestro_calls": total_eval,
        "skipped_calls": total_skip,
        "skip_pct":      round(total_skip/(total_eval+total_skip)*100,1)
                         if total_eval and total_skip else None,
        "final_epsilon": final_eps,
        "q_states":      q_states,
        "folder":        folder,
    }

def collect_results(results_dir):
    rows = []
    for d in sorted(glob.glob(os.path.join(results_dir, "*"))):
        if os.path.isdir(d):
            r = parse_result_dir(d)
            if r:
                rows.append(r)
    return pd.DataFrame(rows)

# ── Sheet helpers ──────────────────────────────────────────────────────────────
def write_raw_sheet(wb, df):
    ws = wb.create_sheet("Raw Results")
    cols = list(df.columns)
    headers = [
        "Model", "Mode", "Q-Table Size", "Epsilon Decay",
        "Best Runtime\n(cycles)", "Best Reward", "Wall Time (s)",
        "MAESTRO Calls", "Skipped Calls", "Skip %",
        "Final ε", "Q-States Known", "Folder"
    ]
    for i, h in enumerate(headers, 1):
        hdr(ws, 1, i, h)

    for r_idx, row in enumerate(df.itertuples(), 2):
        band = BAND_FILL if r_idx % 2 == 0 else None
        vals = [
            row.model, row.mode, row.q_table_size, row.epsilon_decay,
            row.best_runtime_cycles, row.best_reward, row.wall_time_s,
            row.maestro_calls, row.skipped_calls, row.skip_pct,
            row.final_epsilon, row.q_states, row.folder
        ]
        for c_idx, v in enumerate(vals, 1):
            fmt = None
            if c_idx == 5:  fmt = "#,##0"
            if c_idx == 6:  fmt = "0.00E+00"
            if c_idx == 7:  fmt = "0.00"
            if c_idx == 10: fmt = "0.0\"%\""
            cell(ws, r_idx, c_idx, v, fill=band, fmt=fmt)

    set_col_widths(ws, [14,12,14,14,18,16,14,14,14,10,10,14,40])
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 36
    return ws

def write_summary_sheet(wb, df):
    ws = wb.create_sheet("Baseline vs Q-Filter")
    ws.merge_cells("A1:L1")
    c = ws["A1"]
    c.value = "GAMMA: Baseline vs Q-Filter — Summary by Model"
    c.font = Font(name="Arial", bold=True, size=13, color="1F4E79")
    c.alignment = CENTER

    headers = [
        "Model", "Mode", "Q-Table Size", "ε-Decay",
        "Best Runtime\n(cycles)", "Best Reward",
        "CPU Time (s)", "MAESTRO Calls", "Skipped", "Skip %",
        "Final ε", "Q-States"
    ]
    for i, h in enumerate(headers, 1):
        hdr(ws, 2, i, h)

    models = df["model"].unique()
    row_idx = 3
    for model in sorted(models):
        sub = df[df["model"] == model].sort_values(["mode", "q_table_size", "epsilon_decay"])
        first = True
        for _, row in sub.iterrows():
            is_base = row["mode"] == "Baseline"
            bg = GREEN_FILL if is_base else None
            band = BAND_FILL if row_idx % 2 == 0 else None
            fill = bg or band
            vals = [
                model if first else "",
                row["mode"], row["q_table_size"], row["epsilon_decay"],
                row["best_runtime_cycles"], row["best_reward"],
                row["wall_time_s"], row["maestro_calls"],
                row["skipped_calls"], row["skip_pct"],
                row["final_epsilon"], row["q_states"]
            ]
            fmts = [None,None,None,None,"#,##0","0.00E+00","0.00","#,##0","#,##0","0.0","0.000",None]
            for c_idx, (v, fmt) in enumerate(zip(vals, fmts), 1):
                cell(ws, row_idx, c_idx, v, fill=fill, fmt=fmt,
                     font=BOLD_FONT if is_base else BODY_FONT)
            first = False
            row_idx += 1
        # blank separator row
        row_idx += 1

    set_col_widths(ws, [14,12,14,10,18,16,13,14,10,8,8,10])
    ws.freeze_panes = "A3"
    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 36
    return ws

def write_table_size_sheet(wb, df):
    ws = wb.create_sheet("Q-Table Size Effect")
    ws.merge_cells("A1:H1")
    c = ws["A1"]
    c.value = "Effect of Q-Table Size on GAMMA Performance"
    c.font = Font(name="Arial", bold=True, size=12, color="1F4E79")
    c.alignment = CENTER

    headers = ["Model", "Q-Table Size", "Avg ε-Decay",
               "Best Runtime\n(cycles)", "Best Reward",
               "CPU Time (s)", "MAESTRO Calls", "Skip %"]
    for i, h in enumerate(headers, 1):
        hdr(ws, 2, i, h)

    qf = df[df["mode"] == "Q-Filter"].copy()
    grp = qf.groupby(["model", "q_table_size"]).agg(
        avg_eps=("epsilon_decay","mean"),
        best_runtime=("best_runtime_cycles","min"),
        best_reward=("best_reward","max"),
        cpu_time=("wall_time_s","mean"),
        maestro=("maestro_calls","mean"),
        skip_pct=("skip_pct","mean")
    ).reset_index()

    row_idx = 3
    for _, row in grp.iterrows():
        band = BAND_FILL if row_idx % 2 == 0 else None
        vals = [row["model"], row["q_table_size"], round(row["avg_eps"],2),
                row["best_runtime"], row["best_reward"],
                round(row["cpu_time"],2) if pd.notna(row["cpu_time"]) else None,
                int(row["maestro"]) if pd.notna(row["maestro"]) else None,
                round(row["skip_pct"],1) if pd.notna(row["skip_pct"]) else None]
        fmts=[None,None,"0.00","#,##0","0.00E+00","0.00","#,##0","0.0"]
        for c_idx,(v,fmt) in enumerate(zip(vals,fmts),1):
            cell(ws, row_idx, c_idx, v, fill=band, fmt=fmt)
        row_idx += 1

    set_col_widths(ws, [14,14,12,18,16,13,14,10])
    ws.freeze_panes = "A3"
    ws.row_dimensions[2].height = 36
    return ws

def write_epsilon_sheet(wb, df):
    ws = wb.create_sheet("Epsilon Effect")
    ws.merge_cells("A1:H1")
    c = ws["A1"]
    c.value = "Effect of Epsilon Decay on GAMMA Performance"
    c.font = Font(name="Arial", bold=True, size=12, color="1F4E79")
    c.alignment = CENTER

    headers = ["Model", "ε-Decay", "Avg Q-Table Size",
               "Best Runtime\n(cycles)", "Best Reward",
               "CPU Time (s)", "MAESTRO Calls", "Skip %"]
    for i, h in enumerate(headers, 1):
        hdr(ws, 2, i, h)

    qf = df[df["mode"] == "Q-Filter"].copy()
    grp = qf.groupby(["model", "epsilon_decay"]).agg(
        avg_tsize=("q_table_size","mean"),
        best_runtime=("best_runtime_cycles","min"),
        best_reward=("best_reward","max"),
        cpu_time=("wall_time_s","mean"),
        maestro=("maestro_calls","mean"),
        skip_pct=("skip_pct","mean")
    ).reset_index()

    row_idx = 3
    for _, row in grp.iterrows():
        band = BAND_FILL if row_idx % 2 == 0 else None
        vals = [row["model"], row["epsilon_decay"], round(row["avg_tsize"]),
                row["best_runtime"], row["best_reward"],
                round(row["cpu_time"],2) if pd.notna(row["cpu_time"]) else None,
                int(row["maestro"]) if pd.notna(row["maestro"]) else None,
                round(row["skip_pct"],1) if pd.notna(row["skip_pct"]) else None]
        fmts=[None,"0.00","0","#,##0","0.00E+00","0.00","#,##0","0.0"]
        for c_idx,(v,fmt) in enumerate(zip(vals,fmts),1):
            cell(ws, row_idx, c_idx, v, fill=band, fmt=fmt)
        row_idx += 1

    set_col_widths(ws, [14,10,16,18,16,13,14,10])
    ws.freeze_panes = "A3"
    ws.row_dimensions[2].height = 36
    return ws

def write_qtable_guide(wb):
    """Sheet explaining every field of the Q-table."""
    ws = wb.create_sheet("Q-Table Field Guide")
    ws.merge_cells("A1:E1")
    c = ws["A1"]
    c.value = "Q-Table Structure & Field Descriptions"
    c.font = Font(name="Arial", bold=True, size=14, color="1F4E79")
    c.alignment = CENTER

    ws.merge_cells("A2:E2")
    c = ws["A2"]
    c.value = (
        "GAMMA maintains four separate Q-tables (eval, crossover, growth, aging). "
        "Each table maps a genome state-key → Q-value for action=1 (proceed). "
        "Below describes every field used internally."
    )
    c.font = Font(name="Arial", italic=True, size=9)
    c.alignment = LEFT

    section_hdr = [
        ("STATE KEY FIELDS", "A3:E3"),
        ("Q-TABLE VALUE FIELDS", "A10:E10"),
        ("Q-FILTER HYPERPARAMETERS", "A17:E17"),
        ("GENERATION STATS (logged each gen)", "A26:E26"),
    ]

    col_hdrs = ["Field / Parameter", "Type", "Range / Example", "Description", "Role in Decision"]
    for i, h in enumerate(col_hdrs, 1):
        hdr(ws, 4, i, h)

    rows_data = [
        # State key fields
        ("sp_dim",    "str",  "K / C / Y / X",
         "Spatial (parallelized) dimension from position 0 of the genome. "
         "Determines which loop is unrolled across PEs.",
         "Part of state key: sp_dim|loop_order"),
        ("loop_order","tuple","e.g. (K,C,Y,X,R,S)",
         "Ordered tuple of all 6 dimension labels (positions 1–6 of genome). "
         "Encodes the temporal computation order — directly influences data reuse.",
         "Part of state key: sp_dim|loop_order"),
        ("state_key", "str",  "K|KCYXRS",
         "Full hashable state: f'{sp_dim}|{loop_order_string}'. "
         "Used as the dictionary key in Q-tables. Ignores tile sizes to keep state space compact.",
         "Primary Q-table index (key)"),
        ("__separator__","","","",""),
        # Q-table value fields
        ("Q(s, a=1)", "float","e.g. -3.2e5",
         "Stored value for taking action=1 (evaluate/proceed) in state s. "
         "Updated via: Q ← Q + α(R + γ·maxQ(s') − Q). "
         "Negative for valid genomes (reward = −latency in cycles).",
         "Compared to skip_threshold; if Q > threshold → proceed, else skip"),
        ("Q(s, a=0)", "float","implicit 0.0",
         "Value for skipping (action=0). Implicitly 0 — the agent always "
         "compares Q(s,1) vs 0. Never stored explicitly.",
         "Baseline for skip decision"),
        ("table_type","enum", "eval / cross / growth / aging",
         "Which GA phase this Q-table governs. 'eval' gates MAESTRO calls. "
         "Others gate operator application.",
         "Selects which OrderedDict is read/updated"),
        ("__separator__","","","",""),
        # Hyperparameters
        ("alpha (α)",       "float","0.0–1.0 (default 0.1)",
         "Q-learning rate. How aggressively Q-values are updated each step. "
         "High α → fast learning but noisy; low α → stable but slow.",
         "Controls Q-update magnitude"),
        ("gamma (γ)",       "float","0.0–1.0 (default 0.9)",
         "Discount factor for future reward. Near 1 = values long-horizon reward. "
         "Near 0 = myopic, only immediate reward counts.",
         "Scales next-state Q in Bellman equation"),
        ("table_size",      "int",  "100–50000 (sweep: 500,1000,5000,10000)",
         "Maximum number of state-keys per table. Older entries evicted (LRU). "
         "Larger table → more memory, better generalization. "
         "Smaller table → faster lookup, more evictions.",
         "Controls Q-table memory footprint; trade-off: coverage vs. speed"),
        ("epsilon (ε)",     "float","1.0 → epsilon_min",
         "ε-greedy exploration rate. Probability of ignoring Q-table and evaluating anyway. "
         "Starts at 1.0 (full exploration), decays each generation.",
         "Controls explore/exploit balance"),
        ("epsilon_decay",   "float","0.70–0.95 (sweep: 0.70,0.80,0.90)",
         "Multiplicative decay: ε ← max(ε_min, ε × decay) each generation. "
         "0.70 → aggressive exploitation early; 0.90 → slow decay, more exploration.",
         "Determines how quickly the filter becomes selective"),
        ("epsilon_min",     "float","0.10 (fixed)",
         "Floor for ε. Ensures at least 10% random exploration even in late generations "
         "to avoid getting stuck in local optima.",
         "Prevents pure greedy exploitation"),
        ("skip_threshold",  "float","-500,000 (latency objective)",
         "Q(s,1) must exceed this value to proceed during exploitation. "
         "For latency: reward = −runtime_cycles so valid good genomes have Q > −500K. "
         "Tune this after inspecting typical fitness1 values in genome_all.csv.",
         "The 'cut line': only confident good states pass the filter"),
        ("__separator__","","","",""),
        # Generation stats
        ("gen",       "int",  "1..50",         "Generation number.",            "Row index in gen_stats log"),
        ("evaluated", "int",  "0..pop_size",   "Genomes sent to MAESTRO this gen.",  "Tracks cost model calls saved"),
        ("skipped",   "int",  "0..pop_size",   "Genomes skipped by Q-filter this gen.",  "Tracks filter effectiveness"),
        ("epsilon",   "float","ε after decay", "ε value at end of this generation.",  "Logged for convergence analysis"),
        ("q_states",  "int",  "0..table_size", "Number of unique states known in eval Q-table.", "Proxy for exploration coverage"),
    ]

    row_idx = 5
    current_section_rows = {
        0: (5, 8),    # state keys: rows 5-8
        1: (10, 13),  # q values: rows 10-13
        2: (15, 23),  # hyperparams: rows 15-23
        3: (25, 30),  # gen stats: rows 25-30
    }

    # Write section headers
    section_titles = [
        ("A5:E5",  "STATE KEY — How a genome is represented in the Q-table"),
        ("A10:E10","Q-TABLE VALUES — What is stored per state"),
        ("A15:E15","Q-FILTER HYPERPARAMETERS — Tunable settings"),
        ("A25:E25","GENERATION STATISTICS — Logged each generation"),
    ]
    for rng, title in section_titles:
        ws.merge_cells(rng)
        r = int(rng.split(":")[0][1:])
        c_ = ws.cell(row=r, column=1, value=title)
        c_.font = Font(name="Arial", bold=True, size=10, color="FFFFFF")
        c_.fill = SUB_FILL
        c_.alignment = LEFT
        c_.border = MED_BORDER

    data_rows = [
        ("sp_dim","str","K / C / Y / X",
         "Spatial (parallelized) dimension from genome[0][0]. "
         "The loop spatially unrolled across PEs — defines which dimension is mapped to hardware parallelism.",
         "First component of state key"),
        ("loop_order","tuple","e.g. KCYXRS",
         "Concatenated string of dimension labels from genome positions 1–6, in order. "
         "Encodes temporal computation order; determines data reuse pattern (weight/output/input stationary behavior).",
         "Second component of state key; together with sp_dim forms the full state identifier"),
        ("state_key","str","K|KCYXRS",
         "Final hashable key = f'{sp_dim}|{loop_order_str}'. "
         "Tile sizes are intentionally excluded to keep the state space tractable — tile choices vary widely but order/parallelism patterns repeat.",
         "Dictionary key indexing each Q-table (eval/cross/growth/aging)"),
    ]
    r = 6
    for vals in data_rows:
        band = BAND_FILL if r % 2 == 0 else None
        for c_idx, v in enumerate(vals, 1):
            cell(ws, r, c_idx, v, fill=band, align=LEFT if c_idx >= 4 else CENTER)
        r += 1

    hp_rows = [
        ("alpha (α)","float","0.0–1.0 (default: 0.1)",
         "Learning rate. Controls how much each new reward overwrites the existing Q-value. "
         "Low α (0.1) → slow, stable learning. High α (0.5+) → fast but noisy updates.",
         "Scaling factor in Bellman update: Q ← Q + α·(target − Q)"),
        ("gamma (γ)","float","0.0–1.0 (default: 0.9)",
         "Discount factor. Weights the value of the next state. "
         "With γ=0.9, future rewards are nearly as important as immediate ones. "
         "Since GAMMA episodes are short (one generation), high γ helps propagate good genome signals.",
         "Multiplies max Q(s') in the Bellman equation"),
        ("table_size","int","500 / 1000 / 5000 / 10000",
         "Maximum entries per Q-table. Implemented as an LRU OrderedDict: oldest states are evicted when full. "
         "Small size → low memory, fast lookup, but frequent evictions lose learned knowledge. "
         "Large size → retains more states but slower dict operations and more RAM.",
         "Directly controls explore/exploit memory trade-off"),
        ("epsilon (ε)","float","1.0 → epsilon_min (decaying)",
         "Probability of random exploration (ignoring Q-table). At ε=1.0 (gen 1), all genomes are evaluated. "
         "As ε decays, the filter becomes increasingly selective. "
         "ε=0.1 means 90% of decisions use the Q-table.",
         "ε-greedy policy: if rand() < ε → explore (evaluate); else → exploit (check Q vs threshold)"),
        ("epsilon_decay","float","0.70 / 0.80 / 0.90",
         "Multiplicative decay applied to ε each generation. "
         "0.70 → ε halves every ~2 generations (aggressive); 0.90 → ε halves every ~7 generations (gentle). "
         "Faster decay = filter activates sooner but may skip good novel genomes.",
         "Controls how fast exploitation ramps up"),
        ("epsilon_min","float","0.10 (fixed in sweep)",
         "Hard floor for ε. Ensures the filter never becomes 100% greedy. "
         "Keeps 10% exploration alive throughout to handle unseen genome structures.",
         "Prevents premature convergence; maintains diversity in late generations"),
        ("skip_threshold","float","-500,000 (latency objective)",
         "The Q-value cutoff for proceeding. During exploitation: if Q(s,1) > threshold → evaluate; else skip. "
         "For latency objective, reward = −runtime_cycles. Good mappings have reward ≈ −1e5 to −1e6. "
         "Set to −500K to skip states the Q-table has learned are consistently bad (reward << −500K).",
         "Key tuning parameter: too high → over-skipping (misses good genomes); too low → under-filtering (wastes evaluations)"),
    ]
    r = 16
    for vals in hp_rows:
        band = BAND_FILL if r % 2 == 0 else None
        for c_idx, v in enumerate(vals, 1):
            cell(ws, r, c_idx, v, fill=band, align=LEFT if c_idx >= 4 else CENTER)
        r += 1

    stat_rows = [
        ("gen","int","1 .. num_generations","Generation index (1-based)","Row index in printed stats"),
        ("evaluated","int","0 .. population_size",
         "Count of genomes submitted to MAESTRO cost model this generation.",
         "Direct measure of cost model calls (want this low with Q-filter on)"),
        ("skipped","int","0 .. population_size",
         "Count of genomes blocked by Q-filter (not sent to MAESTRO).",
         "Measure of filter effectiveness; higher = more savings"),
        ("epsilon","float","ε_min .. 1.0",
         "ε value after decay at end of this generation.",
         "Convergence indicator: when ε → ε_min, filter is in near-full exploitation mode"),
        ("q_states","int","0 .. table_size",
         "Number of unique state keys currently in the eval Q-table.",
         "Exploration coverage: how many distinct genome structures the filter has learned about"),
    ]
    r = 26
    for vals in stat_rows:
        band = BAND_FILL if r % 2 == 0 else None
        for c_idx, v in enumerate(vals, 1):
            cell(ws, r, c_idx, v, fill=band, align=LEFT if c_idx >= 4 else CENTER)
        r += 1

    set_col_widths(ws, [18, 10, 22, 55, 38])
    ws.row_dimensions[1].height = 30
    ws.row_dimensions[2].height = 45
    return ws

# ── Optimal Values Sheet ───────────────────────────────────────────────────────
def write_optimal_sheet(wb, df):
    ws = wb.create_sheet("Optimal Parameters")
    ws.merge_cells("A1:F1")
    c = ws["A1"]
    c.value = "Optimal Q-Filter Parameters per Model (from Sweep)"
    c.font = Font(name="Arial", bold=True, size=13, color="1F4E79")
    c.alignment = CENTER

    ws.merge_cells("A2:F2")
    c = ws["A2"]
    c.value = (
        "Optimal = configuration achieving best (lowest) runtime with Q-filter enabled. "
        "Compare Q-filter reward against baseline to assess quality retention."
    )
    c.font = Font(name="Arial", italic=True, size=9)
    c.alignment = LEFT

    hdrs = ["Model", "Best Q-Table Size", "Best ε-Decay",
            "Best Runtime\n(cycles)", "Best Reward",
            "vs Baseline\n(reward ratio)"]
    for i, h in enumerate(hdrs, 1):
        hdr(ws, 3, i, h)

    models = df["model"].unique()
    row_idx = 4
    for model in sorted(models):
        base = df[(df["model"] == model) & (df["mode"] == "Baseline")]
        qf   = df[(df["model"] == model) & (df["mode"] == "Q-Filter")]

        base_reward = base["best_reward"].max() if not base.empty else None

        if qf.empty:
            cell(ws, row_idx, 1, model)
            cell(ws, row_idx, 2, "N/A")
            row_idx += 1
            continue

        # Best = highest reward among Q-filter runs
        best_row = qf.loc[qf["best_reward"].idxmax()] if qf["best_reward"].notna().any() else None
        if best_row is None:
            best_row = qf.iloc[0]

        ratio = None
        if base_reward and best_row["best_reward"] and base_reward != 0:
            ratio = best_row["best_reward"] / base_reward

        band = BAND_FILL if row_idx % 2 == 0 else None
        vals = [model, best_row["q_table_size"], best_row["epsilon_decay"],
                best_row["best_runtime_cycles"], best_row["best_reward"], ratio]
        fmts = [None, None, "0.00", "#,##0", "0.00E+00", "0.000"]
        for c_idx, (v, fmt) in enumerate(zip(vals, fmts), 1):
            cl = cell(ws, row_idx, c_idx, v, fill=band, fmt=fmt)
            # Colour ratio: green if ≥ 0.9, yellow if 0.7-0.9, red if < 0.7
            if c_idx == 6 and ratio is not None:
                if ratio >= 0.9:   cl.fill = GREEN_FILL
                elif ratio >= 0.7: cl.fill = YELL_FILL
                else:              cl.fill = PatternFill("solid", start_color="FFB3B3")
        row_idx += 1

    set_col_widths(ws, [14, 16, 14, 18, 16, 18])
    ws.freeze_panes = "A4"
    ws.row_dimensions[3].height = 36
    return ws

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dir", default="./Gamma_frequency/results",
                        help="Directory containing experiment result folders")
    parser.add_argument("--out", default="GAMMA_QFilter_Report.xlsx",
                        help="Output Excel filename")
    args = parser.parse_args()

    print(f"[Excel] Scanning {args.results_dir} ...")
    df = collect_results(args.results_dir)

    if df.empty:
        print("[Excel] No results found. Creating template workbook with field guide only.")
        # Create demo data so sheet structure is valid
        df = pd.DataFrame([{
            "model": "resnet18", "mode": "Baseline", "q_table_size": None,
            "epsilon_decay": None, "best_runtime_cycles": None,
            "best_reward": None, "wall_time_ms": None, "wall_time_s": None,
            "maestro_calls": None, "skipped_calls": None, "skip_pct": None,
            "final_epsilon": None, "q_states": None, "folder": "NOT_RUN_YET"
        }])

    print(f"[Excel] Found {len(df)} experiment records.")

    wb = Workbook()
    wb.remove(wb.active)  # remove default sheet

    write_raw_sheet(wb, df)
    write_summary_sheet(wb, df)
    write_table_size_sheet(wb, df)
    write_epsilon_sheet(wb, df)
    write_qtable_guide(wb)
    write_optimal_sheet(wb, df)

    out_path = args.out
    wb.save(out_path)
    print(f"[Excel] Saved → {out_path}")
    return out_path

if __name__ == "__main__":
    main()
