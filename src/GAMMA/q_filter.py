"""
q_filter.py
===========
Value-based evaluation filter for GAMMA's genetic algorithm.

WHY THIS WAS REWRITTEN
----------------------
The previous mean-EMA version (see git history at d4607dd) did not work,
for reasons that were measured rather than guessed:

  1. It learned E[fitness | state] via a mean EMA, but GA selection consumes
     max[fitness | state]. Measured on alexnet: rho(Q, state mean) = +0.913
     but rho(Q, state best) = +0.370. 98 of the top-100 genomes lived in
     states the filter condemned.
  2. Reward was the raw MAESTRO cycle count, whose distribution is savagely
     heavy-tailed (mean = 166x median). One catastrophic mapping sank a
     state permanently.
  3. skip_threshold was calibrated at the end of generation 1, when every
     Q had had exactly ONE update from zero (Q = alpha*r, a 10x compressed
     scale). As the EMA converged toward r, essentially every state drifted
     below it: 25% below at gen 1 -> 96.6% below at the end.
  4. The gate therefore saturated against its own max_skip_rate cap, and
     from gen 25 onward `random.sample` -- not the Q-table -- chose which
     genomes to spare.

DESIGN OF THE REPLACEMENT
-------------------------
  * REWARD is the within-generation rank of a genome's fitness, in [0,1]
    (0 = worst this generation, 1 = best). Scale-free, comparable across
    models and generations, and immune to the heavy tail.
  * Q(s) is an EXPECTILE (asymmetric EMA) tracking a HIGH QUANTILE of the
    state's reward distribution -- "how good is this state when it does
    well" -- which is the statistic selection actually uses. With
    alpha_up=0.5 / alpha_down=0.02 it converges to roughly the 96th
    expectile.
  * SKIPPING is a per-generation RANK rule: skip the worst `skip_frac` of
    the population by Q. The skip rate is a controlled input, not an
    emergent property of a frozen threshold, so it cannot saturate.
  * A state must be seen `min_visits` times before it is eligible to be
    skipped; unseen states start optimistic (Q = 1.0). Optimism under
    uncertainty, so the filter never culls something it knows nothing about.
  * mode='random' is the null-hypothesis CONTROL ARM: skip the same
    fraction uniformly at random, ignoring Q entirely. If the learned arm
    cannot beat this, the Q-table is contributing nothing.
"""

import random
import json
import os
from collections import OrderedDict

TABLES = ("eval", "cross", "growth", "aging")


class QFilter:
    def __init__(
        self,
        alpha_up=0.4,        # EMA rate when reward BEATS current estimate
        alpha_down=0.05,     # EMA rate when it falls below (asymmetric => high quantile)
        skip_frac=0.35,      # fraction of the population to skip per generation
        min_visits=3,        # visits before a state may be skipped
        epsilon=1.0,         # initial exploration rate
        epsilon_decay=0.9,
        epsilon_min=0.05,
        table_size=10000,
        q_table_path=None,
        mode="qlearn",       # "qlearn" | "random" (control arm)
        good_q=0.60,         # Q above this = "known-good" (guided mutation)
    ):
        self.alpha_up = alpha_up
        self.alpha_down = alpha_down
        self.skip_frac = skip_frac
        self.min_visits = min_visits
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        self.table_size = table_size
        self.q_table_path = q_table_path
        self.mode = mode
        self.good_q = good_q

        self.q = {t: OrderedDict() for t in TABLES}      # state -> Q in [0,1]
        self.n = {t: OrderedDict() for t in TABLES}      # state -> visit count
        self.gen_stats = []

        if q_table_path and os.path.exists(q_table_path):
            self.load(q_table_path)
            print(f"[QFilter] Loaded Q-tables from {q_table_path}")

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    @staticmethod
    def extract_state(indv):
        """State = spatial dim | loop order of the first cluster, e.g. 'K|KCYRXS'."""
        if len(indv) < 7:
            return "UNKNOWN|()"
        return f"{indv[0][0]}|" + "".join(indv[i][0] for i in range(1, 7))

    # ------------------------------------------------------------------
    # Reward shaping
    # ------------------------------------------------------------------
    @staticmethod
    def rank_normalize(values):
        """Map raw fitness values to within-generation ranks in [0,1].

        Ties share the mean rank. A single element maps to 1.0. This is what
        makes the filter scale-free: it never sees a cycle count, only
        'where did this land among its peers this generation'.
        """
        n = len(values)
        if n == 0:
            return []
        if n == 1:
            return [1.0]
        order = sorted(range(n), key=lambda i: values[i])
        out = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and values[order[j + 1]] == values[order[i]]:
                j += 1
            avg = (i + j) / 2.0 / (n - 1)
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    # ------------------------------------------------------------------
    # Q maintenance
    # ------------------------------------------------------------------
    def _trim(self, table_type):
        q, n = self.q[table_type], self.n[table_type]
        while len(q) > self.table_size:
            k, _ = q.popitem(last=False)
            n.pop(k, None)

    def get_q(self, state, table_type="eval"):
        """Optimistic default: an unseen state is assumed best-possible."""
        return self.q[table_type].get(state, 1.0)

    def visits(self, state, table_type="eval"):
        return self.n[table_type].get(state, 0)

    def update(self, state, reward_norm, table_type="eval"):
        """Expectile update toward a high quantile of the state's rewards.

        reward_norm must already be rank-normalized into [0,1].
        """
        q = self.q[table_type]
        if state not in q:
            # FIRST VISIT: seed with the observed reward, do NOT ease down from
            # the optimistic 1.0. Easing down makes Q a function of visit COUNT
            # rather than quality -- with alpha_down=0.02 a state seen 3 times
            # sits at ~0.98 while one seen 300 times sits at ~0.52, so the
            # filter skips whatever is familiar. That is precisely the failure
            # mode this rewrite exists to remove.
            new = reward_norm
        else:
            cur = q[state]
            delta = reward_norm - cur
            alpha = self.alpha_up if delta > 0 else self.alpha_down
            new = cur + alpha * delta

        if state in q:
            del q[state]
        q[state] = new
        self.n[table_type][state] = self.n[table_type].get(state, 0) + 1
        self._trim(table_type)

    # ------------------------------------------------------------------
    # The decision, made for the whole population at once
    # ------------------------------------------------------------------
    def select_evaluate_mask(self, population, table_type="eval"):
        """Return [bool] -- True = send to MAESTRO, False = skip.

        Rank rule: among genomes eligible to be skipped, skip the
        `skip_frac` with the lowest Q. Skip rate is therefore a controlled
        parameter and cannot saturate against a safety cap.
        """
        n_pop = len(population)
        mask = [True] * n_pop
        n_skip = int(n_pop * self.skip_frac)
        if n_skip <= 0:
            return mask

        # Exploration and the min-visits guard both protect a genome from skipping.
        eligible = []
        for i, indv in enumerate(population):
            if random.random() < self.epsilon:
                continue                                   # explore: always evaluate
            s = self.extract_state(indv)
            if self.visits(s, table_type) < self.min_visits:
                continue                                   # too little evidence to cull
            eligible.append(i)

        if not eligible:
            return mask

        if self.mode == "random":
            victims = random.sample(eligible, min(n_skip, len(eligible)))
        else:
            eligible.sort(key=lambda i: self.get_q(self.extract_state(population[i]), table_type))
            victims = eligible[:n_skip]

        for i in victims:
            mask[i] = False
        return mask

    def should_proceed(self, indv, table_type="eval"):
        """Scalar gate for the crossover / growth / aging phases."""
        if self.mode == "random":
            return random.random() >= self.skip_frac
        if random.random() < self.epsilon:
            return True
        s = self.extract_state(indv)
        if self.visits(s, table_type) < self.min_visits:
            return True
        return self.get_q(s, table_type) >= self.skip_frac

    # ------------------------------------------------------------------
    # Bookkeeping
    # ------------------------------------------------------------------
    def end_of_generation(self, gen, n_evaluated, n_skipped):
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
        self.gen_stats.append({
            "gen": gen + 1, "evaluated": n_evaluated, "skipped": n_skipped,
            "epsilon": round(self.epsilon, 4), "q_states": len(self.q["eval"]),
        })
        print(f"[QFilter] Gen {gen+1}: evaluated={n_evaluated}, skipped={n_skipped}, "
              f"eps={self.epsilon:.3f}, states={len(self.q['eval'])}")

    def get_good_loop_orders(self, table_type="eval", top_n=30, threshold=None):
        """(sp_dim, loop_order) pairs for high-Q states -- used by guided mutation.

        Q now lives in [0,1], so `threshold` is a scale-free quantile-like
        cut (default self.good_q) rather than the old raw-cycle number.
        """
        thr = self.good_q if threshold is None else threshold
        q = self.q[table_type]
        good = set()
        for state, val in sorted(q.items(), key=lambda x: x[1], reverse=True)[:top_n]:
            if val < thr or self.visits(state, table_type) < self.min_visits:
                continue
            parts = state.split("|")
            if len(parts) >= 2 and len(parts[1]) == 6:
                good.add((parts[0], tuple(parts[1])))
        return good

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save(self, path=None):
        path = path or self.q_table_path
        if path is None:
            return
        with open(path, "w") as f:
            json.dump({t: {"q": list(self.q[t].items()), "n": list(self.n[t].items())}
                       for t in TABLES}, f, indent=2)
        print(f"[QFilter] Q-tables saved -> {path} (eval states: {len(self.q['eval'])})")

    def load(self, path):
        with open(path) as f:
            data = json.load(f)
        for t in TABLES:
            blob = data.get(t, {})
            if isinstance(blob, dict) and "q" in blob:
                self.q[t] = OrderedDict(blob.get("q", []))
                self.n[t] = OrderedDict(blob.get("n", []))

    def print_summary(self):
        if not self.gen_stats:
            return
        ev = sum(s["evaluated"] for s in self.gen_stats)
        sk = sum(s["skipped"] for s in self.gen_stats)
        tot = ev + sk
        print("\n" + "=" * 60)
        print(f"[QFilter] Run Summary  (mode={self.mode})")
        print(f"  Total candidates generated : {tot}")
        print(f"  Total MAESTRO calls        : {ev}")
        print(f"  Total skipped              : {sk}  ({100*sk/tot if tot else 0:.1f}%)")
        print(f"  Target skip_frac           : {self.skip_frac:.2f}")
        print(f"  Final epsilon              : {self.epsilon:.4f}")
        for t in TABLES:
            print(f"  {t:<6s} states known         : {len(self.q[t])}")
        if self.q["eval"]:
            print("  Top 5 states by Q (eval):")
            for k, v in sorted(self.q["eval"].items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"    {k:20s} Q={v:.3f}  n={self.visits(k)}")
        print("=" * 60 + "\n")
