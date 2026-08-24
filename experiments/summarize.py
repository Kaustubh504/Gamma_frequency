#!/usr/bin/env python3
"""Aggregate experiments/results/*.log into the table for the meeting."""
import re, os, glob, statistics as st
from collections import defaultdict

D = os.path.join(os.path.dirname(__file__), "results")
runs = defaultdict(dict)
for f in glob.glob(os.path.join(D, "*.log")):
    m = re.match(r"(.+)_s(\d+)_(base|qlearn|random)\.log$", os.path.basename(f))
    if not m: continue
    model, seed, arm = m.group(1), int(m.group(2)), m.group(3)
    t = open(f, errors="ignore").read()
    # Whole-model cost = SUM over layers (layer-sequential accelerator).
    # Do NOT use the last "Reward:" line -- that is only the final layer.
    tot = re.findall(r"MODEL TOTAL\s+layers=(\d+)\s+total_runtime=(\d+)", t)
    if not tot: continue                     # crashed / incomplete
    nlayers, cycles = int(tot[-1][0]), float(tot[-1][1])
    real = re.findall(r"REAL_TIME_S=([\d.]+)", t)
    calls = re.findall(r"Total MAESTRO calls\s*:\s*(\d+)", t)
    runs[(model, seed)][arm] = dict(
        reward=-cycles,          # negative: higher is better, as in GAMMA
        layers=nlayers,
        time=float(real[-1]) if real else float("nan"),
        calls=int(calls[-1]) if calls else 10500,
    )

print(f"{'model':<12}{'seed':>5} | {'baseline':>12}{'qlearn':>12}{'random':>12} | {'q>base':>7}{'q>rand':>7}")
print("-" * 76)
qb = qr = n = 0
per_model = defaultdict(lambda: [0, 0, 0])
for (model, seed), d in sorted(runs.items()):
    if len(d) < 3: continue
    b, q, r = d["base"]["reward"], d["qlearn"]["reward"], d["random"]["reward"]
    n += 1
    a, c = q > b, q > r
    qb += a; qr += c
    per_model[model][0] += a; per_model[model][1] += c; per_model[model][2] += 1
    print(f"{model:<12}{seed:>5} | {b:>12.3e}{q:>12.3e}{r:>12.3e} | {str(a):>7}{str(c):>7}")

print("-" * 76)
if n:
    print(f"\nqlearn beats BASELINE : {qb}/{n} runs ({100*qb/n:.0f}%)")
    print(f"qlearn beats RANDOM   : {qr}/{n} runs ({100*qr/n:.0f}%)   <-- the falsification test")
    print("\n  ~50% on the RANDOM row = the learned filter is indistinguishable")
    print("  from random skipping, i.e. the Q-table contributes nothing.\n")
    print(f"{'model':<12}{'q>base':>10}{'q>random':>10}")
    for m, (a, c, tot) in sorted(per_model.items()):
        print(f"{m:<12}{a}/{tot:<8}{c}/{tot}")
    for arm in ("base", "qlearn", "random"):
        ts = [d[arm]["time"] for d in runs.values() if arm in d]
        cs = [d[arm]["calls"] for d in runs.values() if arm in d]
        if ts:
            print(f"\n  {arm:<7} mean wall-clock {st.mean(ts):6.1f}s   mean MAESTRO calls {st.mean(cs):7.0f}")
else:
    print("no complete (model, seed) triples found")
