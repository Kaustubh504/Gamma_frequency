"""
generate_excel_report.py
========================
Reads GAMMA sweep results from results/ directory and produces a
formatted Excel workbook with:
  Sheet 1 – Raw Results              (all experiments, all metrics)
  Sheet 2 – Baseline vs Q-Filter     (per model comparison)
  Sheet 3 – Q-Table Size Effect      (metrics vs table size)
  Sheet 4 – Epsilon Effect           (metrics vs epsilon_decay)
  Sheet 5 – Timing Comparison        (real / user / sys time per experiment)
  Sheet 6 – Guided Mutation Effect   (guided vs non-guided Q-filter)
  Sheet 7 – Optimal Parameters       (best config per model)
  Sheet 8 – Q-Table Field Guide      (description of every Q-table field)
  Sheet 9 – Optimal vs Baseline      (best QF run vs baseline per model, with cycle/CPU ratios)

Run after run_sweep.sh completes:
    python generate_excel_report.py --results_dir ./results
"""

import os
import re
import glob
import argparse
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import (Font, PatternFill, Alignment, Border, Side)
from openpyxl.utils import get_column_letter
from datetime import datetime

# ── Colour palette ─────────────────────────────────────────────────────────────
HDR_FILL   = PatternFill("solid", start_color="1F4E79")
SUB_FILL   = PatternFill("solid", start_color="2E75B6")
BAND_FILL  = PatternFill("solid", start_color="D9E1F2")
GREEN_FILL = PatternFill("solid", start_color="E2EFDA")
YELL_FILL  = PatternFill("solid", start_color="FFF2CC")
ORG_FILL   = PatternFill("solid", start_color="FCE4D6")
RED_FILL   = PatternFill("solid", start_color="FFB3B3")
GREY_FILL  = PatternFill("solid", start_color="D9D9D9")
HDR_FONT   = Font(name="Arial", bold=True, color="FFFFFF", size=10)
BODY_FONT  = Font(name="Arial", size=9)
BOLD_FONT  = Font(name="Arial", bold=True, size=9)
thin       = Side(style="thin",   color="BFBFBF")
MED        = Side(style="medium", color="595959")
BORDER     = Border(left=thin, right=thin, top=thin, bottom=thin)
MED_BORDER = Border(left=MED,  right=MED,  top=MED,  bottom=MED)
CENTER     = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT       = Alignment(horizontal="left",   vertical="center", wrap_text=True)


def hdr(ws, row, col, value, fill=HDR_FILL, font=HDR_FONT, align=CENTER, border=BORDER):
    c = ws.cell(row=row, column=col, value=value)
    c.fill = fill; c.font = font; c.alignment = align; c.border = border
    return c


def cell(ws, row, col, value, fill=None, font=BODY_FONT, align=CENTER,
         border=BORDER, fmt=None):
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
    folder = os.path.basename(path)

    is_qf      = "qfilter" in folder
    is_guided  = "guided"  in folder

    parts = folder.split("_")
    model = parts[0]

    table_size, epsilon = None, None
    if is_qf:
        for p in parts:
            if p.startswith("t") and p[1:].isdigit():
                table_size = int(p[1:])
            if p.startswith("e") and re.match(r"e[\d.]+", p):
                try:
                    epsilon = float(p[1:])
                except ValueError:
                    pass

    # Parse result CSV
    csv_files = glob.glob(os.path.join(path, "**", "result_c.csv"), recursive=True)
    best_runtime = None
    if csv_files:
        try:
            df = pd.read_csv(csv_files[0])
            if "runtime" in df.columns:
                best_runtime = float(df["runtime"].iloc[-1])
        except Exception:
            pass

    # Parse log
    log_file = os.path.join(path, "run.log")
    wall_ms       = None
    total_eval    = None
    total_skip    = None
    final_eps     = None
    q_states      = None
    best_reward   = None
    real_time_s   = None
    user_time_s   = None
    sys_time_s    = None

    if os.path.exists(log_file):
        with open(log_file) as f:
            text = f.read()

        # Legacy wall time (ms) — kept for backward compat
        m = re.search(r"WALL_TIME_MS=(\d+)", text)
        if m:
            wall_ms = int(m.group(1))

        # /usr/bin/time output: real / user / sys
        m = re.search(r"REAL_TIME_S=([\d.]+)", text)
        if m:
            real_time_s = float(m.group(1))
        m = re.search(r"USER_TIME_S=([\d.]+)", text)
        if m:
            user_time_s = float(m.group(1))
        m = re.search(r"SYS_TIME_S=([\d.]+)", text)
        if m:
            sys_time_s = float(m.group(1))

        # Fall back: derive wall_time_s from real_time_s if available
        if real_time_s is not None:
            wall_ms = int(real_time_s * 1000)

        m = re.search(r"Total MAESTRO calls\s*:\s*(\d+)", text)
        if m: total_eval = int(m.group(1))
        m = re.search(r"Total skipped by Q-filter\s*:\s*(\d+)", text)
        if m: total_skip = int(m.group(1))
        m = re.search(r"Final ε\s*:\s*([0-9.]+)", text)
        if m: final_eps = float(m.group(1))
        m = re.search(r"Eval States Known\s*:\s*(\d+)", text)
        if m: q_states = int(m.group(1))
        rewards = re.findall(r"Reward:\s*([-\d.e+]+)", text)
        if rewards:
            try: best_reward = float(rewards[-1])
            except Exception: pass

    wall_s = round(wall_ms / 1000, 2) if wall_ms else None

    return {
        "model":             model,
        "mode":              "Q-Filter+Guided" if (is_qf and is_guided)
                             else ("Q-Filter" if is_qf else "Baseline"),
        "q_guided_mutation": is_guided,
        "q_table_size":      table_size,
        "epsilon_decay":     epsilon,
        "best_runtime_cycles": best_runtime,
        "best_reward":       best_reward,
        "wall_time_s":       wall_s,
        "real_time_s":       real_time_s,
        "user_time_s":       user_time_s,
        "sys_time_s":        sys_time_s,
        "maestro_calls":     total_eval,
        "skipped_calls":     total_skip,
        "skip_pct":          round(total_skip / (total_eval + total_skip) * 100, 1)
                             if total_eval and total_skip else None,
        "final_epsilon":     final_eps,
        "q_states":          q_states,
        "folder":            folder,
    }


def collect_results(results_dir):
    rows = []
    for d in sorted(glob.glob(os.path.join(results_dir, "*"))):
        if os.path.isdir(d):
            r = parse_result_dir(d)
            if r:
                rows.append(r)
    return pd.DataFrame(rows)


# ── Sheet 1: Raw Results ───────────────────────────────────────────────────────
def write_raw_sheet(wb, df):
    ws = wb.create_sheet("Raw Results")
    headers = [
        "Model", "Mode", "Guided\nMutation", "Q-Table Size", "Epsilon Decay",
        "Best Runtime\n(cycles)", "Best Reward",
        "Real Time (s)", "User Time (s)", "Sys Time (s)",
        "MAESTRO Calls", "Skipped Calls", "Skip %",
        "Final ε", "Q-States Known", "Folder"
    ]
    for i, h in enumerate(headers, 1):
        hdr(ws, 1, i, h)

    for r_idx, row in enumerate(df.itertuples(), 2):
        band = BAND_FILL if r_idx % 2 == 0 else None
        vals = [
            row.model, row.mode,
            "Yes" if row.q_guided_mutation else "No",
            row.q_table_size, row.epsilon_decay,
            row.best_runtime_cycles, row.best_reward,
            row.real_time_s, row.user_time_s, row.sys_time_s,
            row.maestro_calls, row.skipped_calls, row.skip_pct,
            row.final_epsilon, row.q_states, row.folder
        ]
        fmts = [None,None,None,None,None,
                "#,##0","0.00E+00",
                "0.00","0.00","0.00",
                "#,##0","#,##0",'0.0"%"',
                "0.000",None,None]
        for c_idx, (v, fmt) in enumerate(zip(vals, fmts), 1):
            fill = GREEN_FILL if row.mode == "Baseline" else (
                   ORG_FILL   if row.q_guided_mutation  else band)
            cell(ws, r_idx, c_idx, v, fill=fill, fmt=fmt)

    set_col_widths(ws, [14,18,10,14,13,18,16,13,13,12,14,13,9,9,14,42])
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 36
    return ws


# ── Sheet 2: Baseline vs Q-Filter Summary ─────────────────────────────────────
def write_summary_sheet(wb, df):
    ws = wb.create_sheet("Baseline vs Q-Filter")
    ws.merge_cells("A1:M1")
    c = ws["A1"]
    c.value = "GAMMA: Baseline vs Q-Filter vs Q-Filter+Guided — Summary by Model"
    c.font = Font(name="Arial", bold=True, size=13, color="1F4E79")
    c.alignment = CENTER

    headers = [
        "Model", "Mode", "Guided", "Q-Table Size", "ε-Decay",
        "Best Runtime\n(cycles)", "Best Reward",
        "Real (s)", "User (s)", "Sys (s)",
        "MAESTRO Calls", "Skip %", "Q-States"
    ]
    for i, h in enumerate(headers, 1):
        hdr(ws, 2, i, h)

    models = df["model"].unique()
    row_idx = 3
    for model in sorted(models):
        sub = df[df["model"] == model].sort_values(
            ["mode", "q_table_size", "epsilon_decay"])
        first = True
        for _, row in sub.iterrows():
            is_base   = row["mode"] == "Baseline"
            is_guided = row["q_guided_mutation"]
            fill = GREEN_FILL if is_base else (ORG_FILL if is_guided else
                   (BAND_FILL if row_idx % 2 == 0 else None))
            vals = [
                model if first else "",
                row["mode"],
                "Yes" if is_guided else "No",
                row["q_table_size"], row["epsilon_decay"],
                row["best_runtime_cycles"], row["best_reward"],
                row["real_time_s"], row["user_time_s"], row["sys_time_s"],
                row["maestro_calls"], row["skip_pct"], row["q_states"]
            ]
            fmts = [None,None,None,None,None,
                    "#,##0","0.00E+00",
                    "0.00","0.00","0.00",
                    "#,##0","0.0",None]
            for c_idx, (v, fmt) in enumerate(zip(vals, fmts), 1):
                cell(ws, row_idx, c_idx, v, fill=fill, fmt=fmt,
                     font=BOLD_FONT if is_base else BODY_FONT)
            first = False
            row_idx += 1
        row_idx += 1  # blank separator

    set_col_widths(ws, [14,18,8,13,9,18,16,10,10,9,13,8,10])
    ws.freeze_panes = "A3"
    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 36
    return ws


# ── Sheet 3: Q-Table Size Effect ──────────────────────────────────────────────
def write_table_size_sheet(wb, df):
    ws = wb.create_sheet("Q-Table Size Effect")
    ws.merge_cells("A1:H1")
    c = ws["A1"]
    c.value = "Effect of Q-Table Size on GAMMA Performance"
    c.font = Font(name="Arial", bold=True, size=12, color="1F4E79")
    c.alignment = CENTER

    headers = ["Model", "Mode", "Q-Table Size", "Avg ε-Decay",
               "Best Runtime\n(cycles)", "Best Reward",
               "Avg Real Time (s)", "Skip %"]
    for i, h in enumerate(headers, 1):
        hdr(ws, 2, i, h)

    qf = df[df["mode"].isin(["Q-Filter", "Q-Filter+Guided"])].copy()
    grp = qf.groupby(["model", "mode", "q_table_size"]).agg(
        avg_eps=("epsilon_decay", "mean"),
        best_runtime=("best_runtime_cycles", "min"),
        best_reward=("best_reward", "max"),
        real_time=("real_time_s", "mean"),
        skip_pct=("skip_pct", "mean")
    ).reset_index()

    row_idx = 3
    for _, row in grp.iterrows():
        is_guided = row["mode"] == "Q-Filter+Guided"
        fill = ORG_FILL if is_guided else (BAND_FILL if row_idx % 2 == 0 else None)
        vals = [row["model"], row["mode"], row["q_table_size"],
                round(row["avg_eps"], 2),
                row["best_runtime"], row["best_reward"],
                round(row["real_time"], 2) if pd.notna(row["real_time"]) else None,
                round(row["skip_pct"], 1) if pd.notna(row["skip_pct"]) else None]
        fmts = [None,None,None,"0.00","#,##0","0.00E+00","0.00","0.0"]
        for c_idx, (v, fmt) in enumerate(zip(vals, fmts), 1):
            cell(ws, row_idx, c_idx, v, fill=fill, fmt=fmt)
        row_idx += 1

    set_col_widths(ws, [14,18,14,12,18,16,16,10])
    ws.freeze_panes = "A3"
    ws.row_dimensions[2].height = 36
    return ws


# ── Sheet 4: Epsilon Effect ────────────────────────────────────────────────────
def write_epsilon_sheet(wb, df):
    ws = wb.create_sheet("Epsilon Effect")
    ws.merge_cells("A1:H1")
    c = ws["A1"]
    c.value = "Effect of Epsilon Decay on GAMMA Performance"
    c.font = Font(name="Arial", bold=True, size=12, color="1F4E79")
    c.alignment = CENTER

    headers = ["Model", "Mode", "ε-Decay", "Avg Q-Table Size",
               "Best Runtime\n(cycles)", "Best Reward",
               "Avg Real Time (s)", "Skip %"]
    for i, h in enumerate(headers, 1):
        hdr(ws, 2, i, h)

    qf = df[df["mode"].isin(["Q-Filter", "Q-Filter+Guided"])].copy()
    grp = qf.groupby(["model", "mode", "epsilon_decay"]).agg(
        avg_tsize=("q_table_size", "mean"),
        best_runtime=("best_runtime_cycles", "min"),
        best_reward=("best_reward", "max"),
        real_time=("real_time_s", "mean"),
        skip_pct=("skip_pct", "mean")
    ).reset_index()

    row_idx = 3
    for _, row in grp.iterrows():
        is_guided = row["mode"] == "Q-Filter+Guided"
        fill = ORG_FILL if is_guided else (BAND_FILL if row_idx % 2 == 0 else None)
        vals = [row["model"], row["mode"], row["epsilon_decay"],
                round(row["avg_tsize"]),
                row["best_runtime"], row["best_reward"],
                round(row["real_time"], 2) if pd.notna(row["real_time"]) else None,
                round(row["skip_pct"], 1) if pd.notna(row["skip_pct"]) else None]
        fmts = [None,None,"0.00","0","#,##0","0.00E+00","0.00","0.0"]
        for c_idx, (v, fmt) in enumerate(zip(vals, fmts), 1):
            cell(ws, row_idx, c_idx, v, fill=fill, fmt=fmt)
        row_idx += 1

    set_col_widths(ws, [14,18,10,16,18,16,16,10])
    ws.freeze_panes = "A3"
    ws.row_dimensions[2].height = 36
    return ws


# ── Sheet 5: Timing Comparison ────────────────────────────────────────────────
def write_timing_sheet(wb, df):
    ws = wb.create_sheet("Timing Comparison")
    ws.merge_cells("A1:J1")
    c = ws["A1"]
    c.value = "Wall-Clock Timing: Real / User / Sys per Experiment"
    c.font = Font(name="Arial", bold=True, size=13, color="1F4E79")
    c.alignment = CENTER

    ws.merge_cells("A2:J2")
    c = ws["A2"]
    c.value = ("Real = wall-clock elapsed time.  "
               "User = CPU time in user space.  "
               "Sys = CPU time in kernel/system calls.  "
               "User+Sys ≈ total CPU work; Real−(User+Sys) ≈ I/O wait.")
    c.font = Font(name="Arial", italic=True, size=9)
    c.alignment = LEFT

    headers = ["Model", "Mode", "Guided", "Q-Table Size", "ε-Decay",
               "Real (s)", "User (s)", "Sys (s)",
               "CPU Total\n(User+Sys)", "MAESTRO\nCalls"]
    for i, h in enumerate(headers, 1):
        hdr(ws, 3, i, h)

    timing_df = df.copy()
    timing_df["cpu_total"] = (
        timing_df["user_time_s"].fillna(0) + timing_df["sys_time_s"].fillna(0)
    ).where(timing_df["user_time_s"].notna() | timing_df["sys_time_s"].notna())

    timing_df = timing_df.sort_values(["model", "mode", "q_table_size", "epsilon_decay"])

    row_idx = 4
    for _, row in timing_df.iterrows():
        is_base   = row["mode"] == "Baseline"
        is_guided = row["q_guided_mutation"]
        fill = GREEN_FILL if is_base else (ORG_FILL if is_guided else
               (BAND_FILL if row_idx % 2 == 0 else None))
        vals = [
            row["model"], row["mode"],
            "Yes" if is_guided else "No",
            row["q_table_size"], row["epsilon_decay"],
            row["real_time_s"], row["user_time_s"], row["sys_time_s"],
            row.get("cpu_total") if "cpu_total" in timing_df.columns else None,
            row["maestro_calls"]
        ]
        fmts = [None,None,None,None,None,
                "0.00","0.00","0.00","0.00","#,##0"]
        for c_idx, (v, fmt) in enumerate(zip(vals, fmts), 1):
            cell(ws, row_idx, c_idx, v, fill=fill, fmt=fmt)
        row_idx += 1

    set_col_widths(ws, [14,18,8,13,9,11,11,11,13,13])
    ws.freeze_panes = "A4"
    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 36
    ws.row_dimensions[3].height = 36
    return ws


# ── Sheet 6: Guided Mutation Effect ───────────────────────────────────────────
def write_guided_sheet(wb, df):
    ws = wb.create_sheet("Guided Mutation Effect")
    ws.merge_cells("A1:K1")
    c = ws["A1"]
    c.value = "Q-Filter vs Q-Filter+Guided Mutation — Side-by-Side Comparison"
    c.font = Font(name="Arial", bold=True, size=13, color="1F4E79")
    c.alignment = CENTER

    headers = ["Model", "Q-Table Size", "ε-Decay",
               "Runtime\n(QF, cycles)", "Runtime\n(Guided, cycles)", "Runtime\nImprovement",
               "Real (QF, s)", "Real (Guided, s)", "Time\nDiff (s)",
               "Skip % (QF)", "Skip % (Guided)"]
    for i, h in enumerate(headers, 1):
        hdr(ws, 2, i, h)

    qf_df = df[df["mode"] == "Q-Filter"].copy()
    gd_df = df[df["mode"] == "Q-Filter+Guided"].copy()

    merged = pd.merge(
        qf_df[["model","q_table_size","epsilon_decay",
               "best_runtime_cycles","real_time_s","skip_pct"]],
        gd_df[["model","q_table_size","epsilon_decay",
               "best_runtime_cycles","real_time_s","skip_pct"]],
        on=["model","q_table_size","epsilon_decay"],
        suffixes=("_qf","_gd"),
        how="outer"
    ).sort_values(["model","q_table_size","epsilon_decay"])

    row_idx = 3
    for _, row in merged.iterrows():
        rt_qf = row["best_runtime_cycles_qf"]
        rt_gd = row["best_runtime_cycles_gd"]
        rt_imp = None
        if pd.notna(rt_qf) and pd.notna(rt_gd) and rt_qf != 0:
            rt_imp = (rt_qf - rt_gd) / rt_qf  # positive = guided is better

        t_qf = row["real_time_s_qf"]
        t_gd = row["real_time_s_gd"]
        t_diff = (t_gd - t_qf) if pd.notna(t_qf) and pd.notna(t_gd) else None

        band = BAND_FILL if row_idx % 2 == 0 else None

        # colour runtime improvement
        imp_fill = band
        if rt_imp is not None:
            if rt_imp > 0.05:    imp_fill = GREEN_FILL
            elif rt_imp < -0.05: imp_fill = RED_FILL
            else:                imp_fill = YELL_FILL

        vals = [
            row["model"], row["q_table_size"], row["epsilon_decay"],
            rt_qf, rt_gd, rt_imp,
            t_qf, t_gd, t_diff,
            row["skip_pct_qf"], row["skip_pct_gd"]
        ]
        fmts = [None,None,"0.00",
                "#,##0","#,##0","0.0%",
                "0.00","0.00","+0.00;-0.00",
                "0.0","0.0"]
        for c_idx, (v, fmt) in enumerate(zip(vals, fmts), 1):
            f = imp_fill if c_idx == 6 else band
            cell(ws, row_idx, c_idx, v, fill=f, fmt=fmt)
        row_idx += 1

    set_col_widths(ws, [14,13,9,18,18,14,13,13,12,12,13])
    ws.freeze_panes = "A3"
    ws.row_dimensions[2].height = 36
    return ws


# ── Sheet 7: Optimal Parameters ───────────────────────────────────────────────
def write_optimal_sheet(wb, df):
    ws = wb.create_sheet("Optimal Parameters")
    ws.merge_cells("A1:H1")
    c = ws["A1"]
    c.value = "Optimal Q-Filter Parameters per Model (from Sweep)"
    c.font = Font(name="Arial", bold=True, size=13, color="1F4E79")
    c.alignment = CENTER

    ws.merge_cells("A2:H2")
    c = ws["A2"]
    c.value = ("Optimal = config achieving highest reward with Q-filter. "
               "Reward ratio = QFilter_reward / Baseline_reward  (green ≥ 0.9, yellow 0.7–0.9, red < 0.7).")
    c.font = Font(name="Arial", italic=True, size=9)
    c.alignment = LEFT

    hdrs = ["Model", "Mode", "Best Q-Table Size", "Best ε-Decay",
            "Best Runtime\n(cycles)", "Best Reward",
            "Baseline\nReward", "Reward\nRatio"]
    for i, h in enumerate(hdrs, 1):
        hdr(ws, 3, i, h)

    models = df["model"].unique()
    row_idx = 4
    for model in sorted(models):
        base = df[(df["model"] == model) & (df["mode"] == "Baseline")]
        base_reward = base["best_reward"].max() if not base.empty else None

        for mode_label in ["Q-Filter", "Q-Filter+Guided"]:
            subset = df[(df["model"] == model) & (df["mode"] == mode_label)]
            if subset.empty:
                continue
            valid = subset[subset["best_reward"].notna()]
            if valid.empty:
                best_row = subset.iloc[0]
            else:
                best_row = valid.loc[valid["best_reward"].idxmax()]

            ratio = None
            if base_reward and pd.notna(best_row["best_reward"]) and base_reward != 0:
                ratio = best_row["best_reward"] / base_reward

            band = BAND_FILL if row_idx % 2 == 0 else None
            vals = [model, mode_label,
                    best_row["q_table_size"], best_row["epsilon_decay"],
                    best_row["best_runtime_cycles"], best_row["best_reward"],
                    base_reward, ratio]
            fmts = [None,None,None,"0.00","#,##0","0.00E+00","0.00E+00","0.000"]
            for c_idx, (v, fmt) in enumerate(zip(vals, fmts), 1):
                cl = cell(ws, row_idx, c_idx, v, fill=band, fmt=fmt)
                if c_idx == 8 and ratio is not None:
                    if ratio >= 0.9:   cl.fill = GREEN_FILL
                    elif ratio >= 0.7: cl.fill = YELL_FILL
                    else:              cl.fill = RED_FILL
            row_idx += 1
        row_idx += 1  # blank between models

    set_col_widths(ws, [14,18,16,12,18,16,16,12])
    ws.freeze_panes = "A4"
    ws.row_dimensions[3].height = 36
    return ws


# ── Sheet 8: Q-Table Field Guide ──────────────────────────────────────────────
def write_qtable_guide(wb):
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

    col_hdrs = ["Field / Parameter", "Type", "Range / Example", "Description", "Role in Decision"]
    for i, h in enumerate(col_hdrs, 1):
        hdr(ws, 4, i, h)

    section_titles = [
        ("A5:E5",  "STATE KEY — How a genome is represented in the Q-table"),
        ("A9:E9",  "Q-TABLE VALUES — What is stored per state"),
        ("A13:E13","Q-FILTER HYPERPARAMETERS — Tunable settings"),
        ("A22:E22","GUIDED MUTATION — How mutation points are selected"),
        ("A27:E27","GENERATION STATISTICS — Logged each generation"),
    ]
    for rng, title in section_titles:
        ws.merge_cells(rng)
        r = int(rng.split(":")[0][1:])
        c_ = ws.cell(row=r, column=1, value=title)
        c_.font = Font(name="Arial", bold=True, size=10, color="FFFFFF")
        c_.fill = SUB_FILL
        c_.alignment = LEFT
        c_.border = MED_BORDER

    state_rows = [
        ("sp_dim", "str", "K / C / Y / X",
         "Spatial (parallelized) dimension from genome[0][0]. "
         "The loop unrolled across PEs — defines hardware parallelism.",
         "First component of state key"),
        ("loop_order", "tuple", "e.g. KCYXRS",
         "Concatenated string of dimension labels from genome positions 1–6. "
         "Encodes temporal computation order; determines data reuse pattern.",
         "Second component of state key"),
        ("state_key", "str", "K|KCYXRS",
         "Final hashable key = f'{sp_dim}|{loop_order_str}'. "
         "Tile sizes excluded to keep state space compact.",
         "Dictionary key indexing each Q-table"),
    ]
    r = 6
    for vals in state_rows:
        band = BAND_FILL if r % 2 == 0 else None
        for c_idx, v in enumerate(vals, 1):
            cell(ws, r, c_idx, v, fill=band, align=LEFT if c_idx >= 4 else CENTER)
        r += 1

    qval_rows = [
        ("Q(s, a=1)", "float", "e.g. -3.2e5",
         "Stored value for taking action=1 (evaluate/proceed) in state s. "
         "Updated via Bellman: Q ← Q + α(R + γ·maxQ(s') − Q). "
         "Negative for latency objective (reward = −cycles).",
         "Compared to skip_threshold; Q > threshold → proceed"),
        ("Q(s, a=0)", "float", "implicit 0.0",
         "Value for skipping (action=0). Always implicitly 0. Never stored.",
         "Baseline for skip decision"),
        ("table_type", "enum", "eval/cross/growth/aging",
         "Which GA phase this Q-table governs. 'eval' gates MAESTRO calls.",
         "Selects which OrderedDict is read/updated"),
    ]
    r = 10
    for vals in qval_rows:
        band = BAND_FILL if r % 2 == 0 else None
        for c_idx, v in enumerate(vals, 1):
            cell(ws, r, c_idx, v, fill=band, align=LEFT if c_idx >= 4 else CENTER)
        r += 1

    hp_rows = [
        ("alpha (α)", "float", "0.0–1.0 (default 0.1)",
         "Learning rate. Controls how much each new reward overwrites Q-value. "
         "Low α → stable, slow. High α → fast, noisy.",
         "Scaling factor in Bellman update"),
        ("gamma (γ)", "float", "0.0–1.0 (default 0.9)",
         "Discount factor. Near 1 = values long-horizon reward. "
         "Near 0 = myopic. High γ helps propagate good genome signals across generations.",
         "Multiplies max Q(s') in Bellman equation"),
        ("table_size", "int", "500/1000/5000/10000",
         "Max entries per Q-table. LRU eviction when full. "
         "Small → fast lookup, more evictions. Large → better coverage, more RAM.",
         "Controls explore/exploit memory trade-off"),
        ("epsilon (ε)", "float", "1.0 → epsilon_min",
         "Exploration rate. At ε=1.0 all genomes evaluated; as ε decays filter becomes selective.",
         "ε-greedy: rand() < ε → explore; else → check Q vs threshold"),
        ("epsilon_decay", "float", "0.70/0.80/0.90",
         "Multiplicative decay per generation. 0.70 → fast exploitation. 0.90 → slow, more exploration.",
         "Controls how quickly the filter becomes selective"),
        ("epsilon_min", "float", "0.10 (fixed)",
         "Floor for ε. Ensures 10% random exploration throughout.",
         "Prevents pure greedy exploitation / premature convergence"),
        ("skip_threshold", "float", "-500,000",
         "Q(s,1) must exceed this to proceed in exploitation mode. "
         "Good latency mappings have reward ≈ −1e5 to −1e6.",
         "The cut-line: only confident good states pass the filter"),
    ]
    r = 14
    for vals in hp_rows:
        band = BAND_FILL if r % 2 == 0 else None
        for c_idx, v in enumerate(vals, 1):
            cell(ws, r, c_idx, v, fill=band, align=LEFT if c_idx >= 4 else CENTER)
        r += 1

    guided_rows = [
        ("q_guided_mutation", "bool", "True / False",
         "Flag enabling guided mutation point selection. "
         "When True, high-Q genome structures are protected from sp_dim mutation; "
         "only tile sizes (positions 1–6) are mutated for known-good loop orders.",
         "Reduces search space by preserving learned good structures"),
        ("good_loop_orders", "set", "{(K, KCYXRS), ...}",
         "Top-N states from eval Q-table with Q > threshold. "
         "Used as whitelist: if genome's (sp_dim, loop_order) is in this set → protected.",
         "Built by get_good_loop_orders(top_n=30) each generation"),
        ("mutation_point", "int", "0–6 (cluster index)",
         "Index within genome cluster selected for mutation. "
         "0 = sp_dim (spatial dimension). 1–6 = tile sizes. "
         "Guided mode skips index 0 for whitelisted genomes.",
         "_get_biased_mutation_pick() returns this index"),
        ("mutate_par skip", "action", "continue",
         "If genome's (sp_dim, loop_order) is in good_loop_orders, "
         "mutate_par() skips that genome entirely (no sp_dim change). "
         "Prevents destroying known-good spatial assignments.",
         "Protects spatial parallelism dimension of high-Q genomes"),
    ]
    r = 23
    for vals in guided_rows:
        band = BAND_FILL if r % 2 == 0 else None
        for c_idx, v in enumerate(vals, 1):
            cell(ws, r, c_idx, v, fill=band, align=LEFT if c_idx >= 4 else CENTER)
        r += 1

    stat_rows = [
        ("gen", "int", "1..num_generations", "Generation index (1-based).", "Row index in stats log"),
        ("evaluated", "int", "0..pop_size",
         "Genomes submitted to MAESTRO this generation.",
         "Direct measure of cost model calls (lower = more savings)"),
        ("skipped", "int", "0..pop_size",
         "Genomes blocked by Q-filter this generation.",
         "Filter effectiveness indicator"),
        ("epsilon", "float", "ε_min..1.0",
         "ε value after decay at end of this generation.",
         "Convergence indicator"),
        ("q_states", "int", "0..table_size",
         "Unique state keys in eval Q-table.",
         "Exploration coverage proxy"),
    ]
    r = 28
    for vals in stat_rows:
        band = BAND_FILL if r % 2 == 0 else None
        for c_idx, v in enumerate(vals, 1):
            cell(ws, r, c_idx, v, fill=band, align=LEFT if c_idx >= 4 else CENTER)
        r += 1

    set_col_widths(ws, [20, 10, 22, 58, 40])
    ws.row_dimensions[1].height = 30
    ws.row_dimensions[2].height = 45
    return ws


# ── Sheet 9: Optimal Q-Filter vs Baseline ────────────────────────────────────
def write_optimal_comparison_sheet(wb, df):
    ws = wb.create_sheet("Optimal vs Baseline")

    ws.merge_cells("A1:J1")
    c = ws["A1"]
    c.value = "Optimal Q-Filter Run vs Baseline — Per-Model Summary"
    c.font = Font(name="Arial", bold=True, size=13, color="1F4E79")
    c.alignment = CENTER

    ws.merge_cells("A2:J2")
    c = ws["A2"]
    c.value = (
        "Optimal QF = Q-Filter config with highest reward per model (across all table sizes / ε-decay / guided). "
        "CPU = User+Sys time (s).  Cycles Ratio = QF÷Base (≤1.0 means QF finds equal or fewer cycles).  "
        "CPU Saved % = (Base−QF)÷Base×100  (positive = QF is faster)."
    )
    c.font = Font(name="Arial", italic=True, size=9)
    c.alignment = LEFT

    col_hdrs = [
        "Model",
        "Baseline\nCycles",
        "Optimal QF\nCycles",
        "Cycles Ratio\n(QF÷Base)",
        "Baseline\nCPU (s)",
        "Optimal QF\nCPU (s)",
        "CPU Saved\n(s)",
        "CPU\nSaved %",
        "CPU Ratio\n(QF÷Base)",
        "Best QF Config",
    ]
    for i, h in enumerate(col_hdrs, 1):
        hdr(ws, 3, i, h)

    def cpu_of(row):
        u = row["user_time_s"]
        s = row["sys_time_s"]
        if pd.notna(u) and pd.notna(s):
            return float(u) + float(s)
        if pd.notna(u):
            return float(u)
        r = row["real_time_s"]
        return float(r) if pd.notna(r) else None

    models   = sorted(df["model"].unique())
    row_idx  = 4
    agg_rows = []

    for model in models:
        base_df = df[(df["model"] == model) & (df["mode"] == "Baseline")]
        qf_df   = df[(df["model"] == model) & (df["mode"].isin(["Q-Filter", "Q-Filter+Guided"]))]

        # Baseline: prefer row with fewest cycles
        base_cycles = base_cpu = None
        if not base_df.empty:
            vb = base_df[base_df["best_runtime_cycles"].notna()]
            br = vb.loc[vb["best_runtime_cycles"].idxmin()] if not vb.empty else base_df.iloc[0]
            base_cycles = float(br["best_runtime_cycles"]) if pd.notna(br["best_runtime_cycles"]) else None
            base_cpu    = cpu_of(br)

        # Best QF: highest reward
        qf_cycles = qf_cpu = None
        config_label = "N/A"
        if not qf_df.empty:
            vq = qf_df[qf_df["best_reward"].notna()]
            if not vq.empty:
                best = vq.loc[vq["best_reward"].idxmax()]
                qf_cycles = float(best["best_runtime_cycles"]) if pd.notna(best["best_runtime_cycles"]) else None
                qf_cpu    = cpu_of(best)
                t = best.get("q_table_size", "?")
                e = best.get("epsilon_decay", "?")
                m = best.get("mode", "?")
                config_label = f"{m}, t={t}, ε={e}"

        cycles_ratio  = (
            (qf_cycles / base_cycles)
            if (qf_cycles is not None and base_cycles is not None and base_cycles != 0)
            else None
        )
        cpu_saved_s   = (
            (base_cpu - qf_cpu)
            if (base_cpu is not None and qf_cpu is not None)
            else None
        )
        cpu_saved_pct = (
            (cpu_saved_s / base_cpu * 100)
            if (cpu_saved_s is not None and base_cpu)
            else None
        )
        cpu_ratio     = (
            (qf_cpu / base_cpu)
            if (qf_cpu is not None and base_cpu is not None and base_cpu != 0)
            else None
        )

        agg_rows.append((base_cycles, qf_cycles, cycles_ratio,
                         base_cpu, qf_cpu, cpu_saved_s, cpu_saved_pct, cpu_ratio))

        band = BAND_FILL if row_idx % 2 == 0 else None
        cr_f = (GREEN_FILL if cycles_ratio is not None and cycles_ratio <= 1.02 else
                YELL_FILL  if cycles_ratio is not None and cycles_ratio <= 1.10 else
                RED_FILL   if cycles_ratio is not None else band)
        cs_f = (GREEN_FILL if cpu_saved_pct is not None and cpu_saved_pct >= 10 else
                YELL_FILL  if cpu_saved_pct is not None and cpu_saved_pct >= 0  else
                RED_FILL   if cpu_saved_pct is not None else band)

        vals = [model, base_cycles, qf_cycles, cycles_ratio,
                base_cpu, qf_cpu, cpu_saved_s, cpu_saved_pct, cpu_ratio, config_label]
        fmts = [None, "#,##0", "#,##0", "0.000",
                "0.00", "0.00", "0.00", "0.0", "0.000", None]
        clrs = [band, band, band, cr_f or band,
                band, band, cs_f or band, cs_f or band, cs_f or band, band]
        for c_idx, (v, fmt, f) in enumerate(zip(vals, fmts, clrs), 1):
            cell(ws, row_idx, c_idx, v, fill=f, fmt=fmt)
        row_idx += 1

    # ── Average row ──────────────────────────────────────────────────────────
    row_idx += 1  # blank spacer

    def _avg(idx):
        vs = [r[idx] for r in agg_rows if r[idx] is not None]
        return sum(vs) / len(vs) if vs else None

    a_bc, a_qc, a_cr = _avg(0), _avg(1), _avg(2)
    a_bu, a_qu        = _avg(3), _avg(4)
    a_ss, a_sp, a_ur  = _avg(5), _avg(6), _avg(7)

    cr_f_avg = (GREEN_FILL if a_cr is not None and a_cr <= 1.02 else
                YELL_FILL  if a_cr is not None and a_cr <= 1.10 else
                RED_FILL   if a_cr is not None else GREY_FILL)
    cs_f_avg = (GREEN_FILL if a_sp is not None and a_sp >= 10 else
                YELL_FILL  if a_sp is not None and a_sp >= 0  else
                RED_FILL   if a_sp is not None else GREY_FILL)

    avg_vals = ["AVERAGE", a_bc, a_qc, a_cr, a_bu, a_qu, a_ss, a_sp, a_ur, ""]
    avg_fmts = [None, "#,##0", "#,##0", "0.000", "0.00", "0.00", "0.00", "0.0", "0.000", None]
    avg_clrs = [GREY_FILL, GREY_FILL, GREY_FILL, cr_f_avg,
                GREY_FILL, GREY_FILL, cs_f_avg, cs_f_avg, cs_f_avg, GREY_FILL]
    for c_idx, (v, fmt, f) in enumerate(zip(avg_vals, avg_fmts, avg_clrs), 1):
        cell(ws, row_idx, c_idx, v, fill=f, fmt=fmt, font=BOLD_FONT)

    set_col_widths(ws, [14, 16, 16, 15, 14, 14, 13, 11, 13, 38])
    ws.freeze_panes = "A4"
    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 50
    ws.row_dimensions[3].height = 54
    return ws


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dir", default="./results",
                        help="Directory containing experiment result folders")
    parser.add_argument("--out", default="GAMMA_QFilter_Report.xlsx",
                        help="Output Excel filename")
    args = parser.parse_args()

    print(f"[Excel] Scanning {args.results_dir} ...")
    df = collect_results(args.results_dir)

    if df.empty:
        print("[Excel] No results found. Creating template workbook.")
        df = pd.DataFrame([{
            "model": "resnet18", "mode": "Baseline",
            "q_guided_mutation": False,
            "q_table_size": None, "epsilon_decay": None,
            "best_runtime_cycles": None, "best_reward": None,
            "wall_time_s": None, "real_time_s": None,
            "user_time_s": None, "sys_time_s": None,
            "maestro_calls": None, "skipped_calls": None,
            "skip_pct": None, "final_epsilon": None,
            "q_states": None, "folder": "NOT_RUN_YET"
        }])

    print(f"[Excel] Found {len(df)} experiment records.")
    print(f"[Excel]   Baseline:          {len(df[df['mode']=='Baseline'])}")
    print(f"[Excel]   Q-Filter:          {len(df[df['mode']=='Q-Filter'])}")
    print(f"[Excel]   Q-Filter+Guided:   {len(df[df['mode']=='Q-Filter+Guided'])}")

    wb = Workbook()
    wb.remove(wb.active)

    write_raw_sheet(wb, df)
    write_summary_sheet(wb, df)
    write_table_size_sheet(wb, df)
    write_epsilon_sheet(wb, df)
    write_timing_sheet(wb, df)
    write_guided_sheet(wb, df)
    write_optimal_sheet(wb, df)
    write_qtable_guide(wb)
    write_optimal_comparison_sheet(wb, df)

    wb.save(args.out)
    print(f"[Excel] Saved → {args.out}")
    return args.out


if __name__ == "__main__":
    main()
