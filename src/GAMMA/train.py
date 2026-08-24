import copy
import argparse
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import glob
import os, sys
script_dir = os.path.dirname(__file__)
module_path = os.path.abspath(os.path.join(script_dir, '../'))
project_path = os.path.abspath(os.path.join(script_dir, '../../'))
if module_path not in sys.path:
    sys.path.insert(0, module_path)
if project_path not in sys.path:
    sys.path.insert(0, project_path)
from utils import *
import gamma as gamma
# from Gamma_frequency.src.GAMMA.q_filter_old import QFilter
from q_filter import QFilter
from math import ceil
import importlib
from shutil import copyfile

fitness_list = None
fitness = None
stage_idx = 0
prev_stage_value = []
tune_iter = 1
opt = None
MAC_AREA_MAESTRO = 4470
MAC_AREA_INT8 = 282
BUF_AREA_perbit = 0.086
L2BUF_AREA_MAESTRO = 4161.536
L1BUF_AREA_MAESTRO = 4505.1889
L2BUF_UNIT = 32768
L1BUF_UNIT = 64

bias = {"par": {1: "K", 2: "C"}, "order": {1: ["K", "C", "Y", "X"], 2: ["K", "C", "Y", "X"]}}


def save_genome_csv(genome_seq_fitness, genome_all_records, outdir=".", layer_idx=0):
    import csv
    os.makedirs(outdir, exist_ok=True)

    genome_all_path = os.path.join(outdir, "genome_all.csv")
    genome_best_path = os.path.join(outdir, "genome_best.csv")

    for r in genome_all_records:
        r["layer"] = layer_idx + 1
    for r in genome_seq_fitness.values():
        r["layer"] = layer_idx + 1

    write_header = (layer_idx == 0)

    if genome_all_records:
        all_keys = []
        seen = set()
        for r in genome_all_records:
            for k in r:
                if k not in seen:
                    all_keys.append(k)
                    seen.add(k)

        mode = "w" if write_header else "a"
        with open(genome_all_path, mode, newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
            if write_header:
                writer.writeheader()
            for r in genome_all_records:
                writer.writerow(r)

        print(f"[GAMMA] Layer {layer_idx+1}: genome_all.csv ({len(genome_all_records)} rows)")

    else:
        print("[DEBUG] genome_all_records EMPTY → using fallback")
        with open(genome_all_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["genome_str", "fitness1"])
            for genome, record in genome_seq_fitness.items():
                writer.writerow([str(genome), record["fitness1"]])
        print(f"[GAMMA] Saved fallback genome_all.csv ({len(genome_seq_fitness)} rows)")

    best_records = sorted(
        genome_seq_fitness.values(),
        key=lambda r: r["fitness1"] if r["fitness1"] != float("-Inf") else -1e18,
        reverse=True
    )
    if best_records:
        # Union the keys across ALL records, not just the first. With a variable
        # level of parallelism (paper system S3 allows 2 or 3 levels) genomes
        # have different field sets, and taking only best_records[0].keys()
        # crashes on the first record that carries L3_* fields.
        keys, seen = [], set()
        for r in best_records:
            for k in r:
                if k not in seen:
                    keys.append(k); seen.add(k)
        with open(genome_best_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            for r in best_records:
                writer.writerow(r)
        print(f"[GAMMA] Saved genome_best.csv ({len(best_records)} rows)")


def get_pe_usage(env, sol, num_pe):
    util_num_pe = num_pe
    baseline = env.get_indiv_info(sol, num_pe=num_pe)
    best_runtime, best_throughput, best_energy, best_area, best_l1_size, best_l2_size, best_mac, best_power, best_num_pe = baseline
    baseline = np.array(baseline)[:-2]
    for i in range(num_pe - 1):
        util_num_pe -= 1
        cur = env.get_indiv_info(sol, num_pe=util_num_pe)
        best_runtime, best_throughput, best_energy, best_area, best_l1_size, best_l2_size, best_mac, best_power, best_num_pe = cur
        cur = np.array(cur)[:-2]
        if sum(baseline != cur) > 1:
            util_num_pe += 1
            break
    return util_num_pe


def train_model(model_defs, input_arg, map_cstr=None, chkpt_file='./chkpt'):
    global opt
    opt = input_arg
    fitness = [opt.fitness1, opt.fitness2]
    dimension = model_defs[0]

    # ── Evaluation filter ─────────────────────────────────────────────────
    # Without --use_qfilter, GAMMA runs identically to the original: every
    # genome goes to MAESTRO. With it, a rank rule skips the worst
    # --skip_frac of each generation by learned Q. Use --filter_mode random
    # as the control arm: same skip rate, no learning.
    q_table_path = os.path.join(os.path.dirname(chkpt_file), "q_table.json")

    if getattr(opt, 'use_qfilter', False):
        q_filter = QFilter(
            alpha_up=opt.alpha_up,
            alpha_down=opt.alpha_down,
            skip_frac=opt.skip_frac,
            min_visits=opt.min_visits,
            epsilon=1.0,
            epsilon_decay=opt.epsilon_decay,
            epsilon_min=opt.epsilon_min,
            table_size=opt.q_table_size,
            q_table_path=q_table_path,
            mode=opt.filter_mode,
            good_q=opt.good_q,
        )
        print(f"[QFilter] ENABLED  mode={opt.filter_mode}  skip_frac={opt.skip_frac} "
              f"-- Q-table: {q_table_path}")
    else:
        q_filter = None
        print("[QFilter] DISABLED - baseline mode (all genomes evaluated)")
    # ─────────────────────────────────────────────────────────────────────

    env = gamma.GAMMA(
        dimension=dimension,
        num_pe=opt.num_pe,
        fitness=fitness,
        par_RS=opt.parRS,
        l1_size=opt.l1_size,
        l2_size=opt.l2_size,
        NocBW=opt.NocBW,
        offchipBW=opt.offchipBW,
        slevel_min=opt.slevel_min,
        slevel_max=opt.slevel_max,
        fixedCluster=opt.fixedCluster,
        log_level=opt.log_level,
        map_cstr=map_cstr,
        q_filter=q_filter,  # None = disabled, runs identically to original
    )

    # Wire Q-guided mutation flag (only effective if q_filter is also enabled)
    env.q_guided_mutation = getattr(opt, 'q_guided_mutation', False)
    env.min_tile_size = getattr(opt, 'min_tile_size', 4)
    if env.q_guided_mutation and q_filter is not None:
        print("[QFilter] Q-guided mutation ENABLED — high-Q genome structures protected from sp_dim mutation")
    elif env.q_guided_mutation and q_filter is None:
        print("[QFilter] WARNING: --q_guided_mutation has no effect without --use_qfilter")

    constraints = {"area": opt.area_budget * 1e6}

    # Enforce buffer capacity limits: reject mappings whose analytically-estimated
    # working set exceeds L1 (per-PE) or L2 (global shared) hardware limits.
    # Without this, MAESTRO22_noRScstr accepts giant-tile mappings (e.g. X=224,Y=224)
    # and reports impossibly low cycle counts (11-12 cycles for VGG16).
    ext_mem_cstr = None
    if opt.l1_size > 0 and opt.l2_size > 0:
        ext_mem_cstr = {"L2-soft": opt.l2_size, "L1-soft": opt.l1_size}

    all_layer_results = []
    for layer_idx, dimension in enumerate(model_defs):
        env.reset_dimension(fitness=fitness, constraints=constraints, dimension=dimension,
                            external_mem_cstr=ext_mem_cstr)
        env.reset_hw_parm(
            num_pe=opt.num_pe,
            l1_size=opt.l1_size,
            l2_size=opt.l2_size,
            pe_limit=opt.pe_limit,
            area_pebuf_only=False,
            external_area_model=True
        )

        # env.run() = full GA loop:
        #   reinit_pop → per generation:
        #     select_parents → crossover_tile → swap_order → mutate_tile →
        #     mutate_pe → mutate_par → born_cluster → kill_cluster →
        #     correctify_tile_dependency → comform_to_cstr → elite injection →
        #     evaluate (Q-filter gates MAESTRO calls here) → genome freq logging
        chkpt, pops = env.run(
            dimension,
            stage_idx=0,
            num_population=opt.num_pop,
            prev_stage_value=None,
            num_generations=opt.epochs,
            best_sol_1st=None,
            init_pop=None,
            bias=None,
            uni_base=False,   # random init: paper uses random initial population
            use_factor=False,
            use_pleteau=False
        )

        save_genome_csv(
            chkpt["genome_seq_fitness"],
            chkpt["genome_all_records"],
            outdir=os.path.dirname(chkpt_file),
            layer_idx=layer_idx
        )

        best_sol = chkpt["best_sol"]
        best_runtime, best_throughput, best_energy, best_area, best_l1_size, best_l2_size, best_mac, best_power, best_num_pe = env.get_indiv_info(best_sol, num_pe=None)

        print("Mapping:", chkpt["best_sol"])
        print(
            f"Reward: {chkpt['best_reward'][0]:.3e}, "
            f"Runtime: {best_runtime:.0f}(cycles), "
            f"Area: {best_area/1e6:.3f}(mm2), "
            f"PE Area_ratio: {best_num_pe*MAC_AREA_INT8/best_area*100:.1f}%, "
            f"Num_PE: {best_num_pe:.0f}, "
            f"L1 Buffer: {best_l1_size:.0f}(elements), "
            f"L2 Buffer: {best_l2_size:.0f}(elements)"
        )

        chkpt_save = {
            "reward": chkpt['best_reward'][0],
            "best_sol": best_sol,
            "runtime": best_runtime,
            "area": best_area,
            "pe_area_ratio": best_num_pe * MAC_AREA_INT8 / best_area,
            "PE": best_num_pe,
            "PE_area": best_num_pe * MAC_AREA_INT8,
            "L1_area": best_l1_size * best_num_pe * BUF_AREA_perbit * 8,
            "L2_area": best_l2_size * BUF_AREA_perbit * 8,
            "L1_size": best_l1_size,
            "L2_size": best_l2_size
        }
        # Accumulate one row PER LAYER. The previous code wrote result_c.csv
        # inside the loop with a fixed filename, so a multi-layer (full-model)
        # run silently kept only the LAST layer's result.
        chkpt_save["layer"] = layer_idx + 1
        all_layer_results.append(chkpt_save)

        columns = ["layer", "runtime", "area", "pe_area_ratio", "PE", "L1_size",
                   "L2_size", "PE_area", "L1_area", "L2_area", "best_sol"]
        rows = [[r[c] for c in columns[:-1]] + [f'{r["best_sol"]}']
                for r in all_layer_results]
        df = pd.DataFrame(rows, columns=columns)
        df.to_csv(chkpt_file[:-4] + ".csv", index=False)

        with open(chkpt_file, "wb") as fd:
            pickle.dump(all_layer_results, fd)


    # ── Whole-model summary ────────────────────────────────────────────────
    # A layer-sequential accelerator runs layers one after another, so the
    # model-level cost is the SUM over layers, not the last layer's value.
    if all_layer_results:
        total_cycles = sum(float(r["runtime"]) for r in all_layer_results)
        max_area = max(float(r["area"]) for r in all_layer_results)
        print("=" * 66)
        print(f"[GAMMA] MODEL TOTAL  layers={len(all_layer_results)}  "
              f"total_runtime={total_cycles:.0f}(cycles)  peak_area={max_area/1e6:.3f}(mm2)")
        print("=" * 66)


def get_cstr_name(mapping_cstr):
    if mapping_cstr:
        cstr_name = mapping_cstr
    else:
        cstr_name = "free"
    return cstr_name