# Ablation results — single layer, pop=200, gen=50, edge platform (168 PE / 512B / 108KB)

Arms: `base` (no filter) · `qlearn` (learned filter) · `random` (control: same
skip rate, no learning). Reward = negative cycles; higher is better.
All runs post-elitism-fix (commit fd9972c).

| model   | seed | baseline   | qlearn     | random     | skip% | q>base | q>rand |
|---------|-----:|-----------:|-----------:|-----------:|------:|:------:|:------:|
| BERT_m  |   42 | -1.422e+06 | -1.442e+06 | -9.851e+05 | 30.0  |   no   |   no   |
| BERT_m  |    7 | -1.180e+06 | -1.530e+06 | -1.097e+06 | 30.1  |   no   |   no   |
| BERT_m  |  123 | -1.467e+06 | -1.219e+06 | -1.312e+06 | 30.0  |  yes   |  yes   |
| ncf_m   |   42 | -1.610e+02 | -1.610e+02 | -1.370e+02 | 28.3  |   no   |   no   |
| ncf_m   |    7 | -1.630e+02 | -2.130e+02 | -2.180e+02 | 28.7  |   no   |  yes   |
| ncf_m   |  123 | -1.370e+02 | -1.570e+02 | -1.590e+02 | 28.4  |   no   |  yes   |
| alexnet |   42 | -1.939e+04 | -3.410e+04 | -2.189e+04 | 31.4  |   no   |   no   |
| alexnet |    7 | -1.978e+04 | -4.180e+04 | -3.951e+04 | 31.5  |   no   |   no   |
| alexnet |  123 | -2.381e+04 | -1.920e+04 | -3.763e+04 | 31.4  |  yes   |  yes   |

**qlearn beats random: 4/9 (44%).** Under a coin-flip null, P(X<=4 of 9) = 0.50 —
indistinguishable from chance. No learning signal in CNN, NLP, or recommendation.

**qlearn beats baseline: 2/9.** One-sided p ~ 0.09; weakly suggests the filter
hurts rather than being neutral.

## What did work

Skip rate is now 28-31% across all three workload classes, on a target of 0.35.
In the original implementation it was an emergent property: 5-10% on CNNs,
62-74% on NLP, and it saturated against the max_skip_rate cap from generation 25
onward. The rank rule makes it a controlled input. The mechanism is sound; the
signal is not there.

## Why the signal is not there

Measured on alexnet:
  - rho(Q, state MEAN fitness) = +0.913   <- what an EMA learns
  - rho(Q, state BEST fitness) = +0.370   <- what GA selection consumes
  - Within one state, fitness spans 5 orders of magnitude, and nearly every
    high-traffic state contains a near-optimal member.
  - 98 of the top-100 genomes lived in states the ORIGINAL filter condemned,
    including the global best.

The discriminating signal is in tile sizes, which the state deliberately
excludes; including them explodes the table (reverted in 49201c5).

## Limitations

Single layer per model, 3 seeds, 3 models. `experiments/ablation.sh` runs the
full-model, all-layers version at paper fidelity.
