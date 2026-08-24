from train import *
import argparse
import os
import pandas as pd
from datetime import datetime

DEVELOP_MODE = False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument('--fitness1', type=str, default="latency",
                        choices=('latency', 'energy', 'power', 'EDP', 'area'))
    parser.add_argument('--fitness2', type=str, default="energy",
                        choices=('latency', 'energy', 'power', 'EDP', 'area'))

    parser.add_argument('--num_pop', type=int, default=20)
    parser.add_argument('--parRS', default=False, action='store_true')
    parser.add_argument('--epochs', type=int, default=20)
    parser.add_argument('--outdir', type=str, default="outdir")

    parser.add_argument('--num_pe', type=int, default=1024)
    parser.add_argument('--l1_size', type=int, default=-1)
    parser.add_argument('--l2_size', type=int, default=-1)
    parser.add_argument('--NocBW', type=int, default=-1)
    parser.add_argument('--offchipBW', type=int, default=-1)

    parser.add_argument('--model', type=str, default="resnet18")
    parser.add_argument('--num_layer', type=int, default=1)

    parser.add_argument('--slevel_min', type=int, default=2)
    parser.add_argument('--slevel_max', type=int, default=2)

    parser.add_argument('--fixedCluster', type=int, default=0)
    parser.add_argument('--log_level', type=int, default=1)
    # ---- Evaluation filter -------------------------------------------------
    parser.add_argument('--use_qfilter', action='store_true',
                        help='Enable the learned evaluation filter')
    parser.add_argument('--filter_mode', type=str, default='qlearn',
                        choices=('qlearn', 'random'),
                        help="'qlearn' = rank-rule filter driven by learned Q; "
                             "'random' = CONTROL ARM that skips the same fraction "
                             "uniformly at random. If qlearn cannot beat random, "
                             "the Q-table is contributing nothing.")
    parser.add_argument('--skip_frac', type=float, default=0.35,
                        help='Fraction of the population to skip per generation. '
                             'This is now a controlled input, not an emergent rate.')
    parser.add_argument('--min_visits', type=int, default=3,
                        help='Times a state must be seen before it may be skipped')
    parser.add_argument('--alpha_up', type=float, default=0.4,
                        help='EMA rate when a reward beats the current estimate')
    parser.add_argument('--alpha_down', type=float, default=0.05,
                        help='EMA rate when it falls below. alpha_up >> alpha_down '
                             'makes Q track a HIGH QUANTILE (what selection uses) '
                             'rather than the mean (what the old version learned).')
    parser.add_argument('--epsilon_decay', type=float, default=0.90)
    parser.add_argument('--epsilon_min', type=float, default=0.05)
    parser.add_argument('--q_table_size', type=int, default=10000)
    parser.add_argument('--good_q', type=float, default=0.60,
                        help='Q above this marks a state known-good for guided mutation')
    parser.add_argument('--q_guided_mutation', action='store_true',
                        help='Protect high-Q genome structures from sp_dim mutation '
                             '(requires --use_qfilter)')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--min_tile_size', type=int, default=4,
                        help='Minimum tile size for any loop dimension')

    parser.add_argument('--costmodel_cstr', type=str, default='maestro_cstr')
    parser.add_argument('--area_budget', type=float, default=-1)
    parser.add_argument('--pe_limit', type=int, default=-1)

    # 🔥 NEW FLAG
    opt = parser.parse_args()

    # Fix all random seeds for reproducibility
    import random as _random
    import numpy as _np
    _random.seed(opt.seed)
    _np.random.seed(opt.seed)
    print(f"[GAMMA] Random seed set to {opt.seed}")

    history_path = '../../'
    m_file = f"../../data/model/{opt.model}.csv"

    df = pd.read_csv(m_file)
    model_defs = df.to_numpy()

    if opt.num_layer:
        model_defs = model_defs[:opt.num_layer]

    now = datetime.now()
    exp_name = f"GAMMA_{opt.model}_GEN-{opt.epochs}_POP-{opt.num_pop}"
    outdir = os.path.join(history_path, opt.outdir, exp_name)

    os.makedirs(outdir, exist_ok=True)

    chkpt_file = os.path.join(outdir, "result_c.plt")

    train_model(model_defs, opt, chkpt_file=chkpt_file)