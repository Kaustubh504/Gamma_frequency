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
    #
# 🔥 Q-LEARNING PARAMETERS
    parser.add_argument('--q_table_size', type=int, default=10000,
                        help='Maximum size of the Q-table')
    parser.add_argument('--q_alpha', type=float, default=0.1,
                        help='Learning rate (alpha) for Q-learning')
    parser.add_argument('--q_gamma', type=float, default=0.9,
                        help='Discount factor (gamma) for Q-learning')
    parser.add_argument('--epsilon_decay', type=float, default=0.90,
                        help='Decay rate for epsilon-greedy exploration')
    #
    parser.add_argument('--costmodel_cstr', type=str, default='maestro_cstr')
    parser.add_argument('--area_budget', type=float, default=-1)
    parser.add_argument('--pe_limit', type=int, default=-1)

    # 🔥 NEW FLAG
    parser.add_argument('--use_qfilter', action='store_true',
                        help='Enable Q-learning filter')

    parser.add_argument('--q_guided_mutation', action='store_true',
                        help='Enable Q-value guided mutation point selection '
                             '(requires --use_qfilter). High-Q genome structures '
                             'are protected from sp_dim mutations; only tile sizes '
                             'are mutated for known-good loop orders.')

    parser.add_argument('--epsilon_min', type=float, default=0.10,
                        help='Minimum epsilon for Q-filter exploration (default: 0.10)')
    parser.add_argument('--auto_threshold', action='store_true', default=True,
                        help='Auto-tune skip_threshold from gen-1 rewards (default: on)')
    parser.add_argument('--threshold_percentile', type=float, default=25.0,
                        help='Reward percentile for auto skip_threshold (default: 25)')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed for reproducibility (default: 42)')

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