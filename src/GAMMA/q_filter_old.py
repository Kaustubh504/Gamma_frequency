"""
q_filter.py
============
Q-Learning filter for GAMMA's genetic algorithm.

Maintains a Q-table keyed on genome state = (sp_dim, loop_order_tuple).
Before MAESTRO is called for a candidate genome, the filter decides:
    action=1 → evaluate (call MAESTRO)
    action=0 → skip    (return cached -Inf, no MAESTRO call)

Update rule (no next-state, no gamma):
    Q(s, 1) ← Q(s, 1) + α * [reward - Q(s, 1)]

Decision rule (ε-greedy):
    with prob ε     → always evaluate (explore)
    with prob (1-ε) → follow Q-table  (exploit)
        if Q(s,1) > threshold → evaluate
        else                  → skip

The Q-table persists across layers and generations within one GAMMA run.
It can also be saved/loaded across runs for warm-starting.
"""

import random
import json
import os


class QFilter:
    def __init__(
        self,
        alpha=0.1,          # learning rate
        epsilon=1.0,        # initial exploration rate (1.0 = evaluate everything at first)
        epsilon_decay=0.9,  # multiply epsilon by this after each generation
        epsilon_min=0.10,   # floor for epsilon (never go fully greedy)
        skip_threshold=0.0, # Q(s,1) must exceed this to evaluate; below = skip
        q_table_path=None,  # optional path to save/load Q-table across runs
    ):
        self.alpha = alpha
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        self.skip_threshold = skip_threshold
        self.q_table_path = q_table_path

        # Q-table: { state_key : float }
        # state_key = string repr of (sp_dim, loop_order_tuple)
        # Q[state] = Q(s, action=1) — value of evaluating this genome type
        # Q(s, action=0) is always 0 by definition (skip = no information)
        self.q_table = {}

        # Stats per generation for logging
        self.gen_stats = []   # list of dicts: {gen, evaluated, skipped, epsilon}

        if q_table_path and os.path.exists(q_table_path):
            self.load(q_table_path)
            print(f"[QFilter] Loaded Q-table from {q_table_path} ({len(self.q_table)} states)")

    # ------------------------------------------------------------------
    # State extraction
    # ------------------------------------------------------------------
    def extract_state(self, indv):
        """
        Extract a compact hashable state from a genome individual.

        State = (sp_dim_L1, loop_order_L1)
        Example: ("K", ("S", "R", "K", "Y", "X", "C"))

        We use only L1 (the first 7 genes) because:
        - It captures the dominant parallelization dimension
        - It captures the loop ordering which most affects data reuse
        - Tile sizes are intentionally excluded — same order/sp with
          different tile sizes should share Q-table entries (generalize)
        - Keeps state space small and tractable
        """
        if len(indv) < 7:
            return ("UNKNOWN", ())
        sp_dim = indv[0][0]                          # e.g. "K"
        loop_order = tuple(indv[i][0] for i in range(1, 7))  # e.g. ("S","R","K","Y","X","C")
        return (sp_dim, loop_order)

    def _state_key(self, state):
        """Convert state tuple to a JSON-serializable string key."""
        sp_dim, loop_order = state
        return f"{sp_dim}|{''.join(loop_order)}"

    # ------------------------------------------------------------------
    # Core Q-table operations
    # ------------------------------------------------------------------
    def get_q_value(self, state):
        """Return Q(s, action=1). Default = 0.0 (neutral, unknown state)."""
        key = self._state_key(state)
        return self.q_table.get(key, 0.0)

    def update(self, state, reward):
        """
        Update Q(s, action=1) after receiving a real MAESTRO reward.

        Q(s,1) ← Q(s,1) + α * [reward - Q(s,1)]

        This is a running exponential moving average of observed rewards
        for this genome state. No γ because evaluation is one-shot.

        Args:
            state:  extracted state tuple
            reward: float — fitness1 value from MAESTRO,
                    or a large negative number if MAESTRO rejected it
        """
        key = self._state_key(state)
        old_q = self.q_table.get(key, 0.0)
        new_q = old_q + self.alpha * (reward - old_q)
        self.q_table[key] = new_q

    # ------------------------------------------------------------------
    # Decision: should we evaluate this genome?
    # ------------------------------------------------------------------
    def should_evaluate(self, indv):
        """
        ε-greedy decision for one candidate genome.

        Returns:
            True  → call MAESTRO (evaluate)
            False → skip (don't call MAESTRO)

        Logic:
            roll = random float in [0, 1)
            if roll < ε:       always evaluate (explore)
            else:
                q = Q(s, 1)
                if q > threshold:  evaluate (exploit — known-good region)
                else:              skip     (exploit — known-bad region)
        """
        if random.random() < self.epsilon:
            return True   # explore: always evaluate

        state = self.extract_state(indv)
        q_val = self.get_q_value(state)
        return q_val > self.skip_threshold   # exploit Q-table

    # ------------------------------------------------------------------
    # After each generation: decay epsilon, log stats
    # ------------------------------------------------------------------
    def end_of_generation(self, gen, n_evaluated, n_skipped):
        """
        Call this once per generation after all evaluations are done.
        Decays epsilon and logs stats.

        Args:
            gen:         generation index (0-based)
            n_evaluated: how many genomes were actually sent to MAESTRO
            n_skipped:   how many genomes were filtered out by Q-table
        """
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
        stat = {
            "gen":        gen + 1,
            "evaluated":  n_evaluated,
            "skipped":    n_skipped,
            "epsilon":    round(self.epsilon, 4),
            "q_states":   len(self.q_table),
        }
        self.gen_stats.append(stat)
        print(
            f"[QFilter] Gen {gen+1}: evaluated={n_evaluated}, skipped={n_skipped}, "
            f"ε={self.epsilon:.3f}, Q-states known={len(self.q_table)}"
        )

    # ------------------------------------------------------------------
    # Save / load Q-table across runs (warm-starting)
    # ------------------------------------------------------------------
    def save(self, path=None):
        path = path or self.q_table_path
        if path is None:
            return
        with open(path, "w") as f:
            json.dump(self.q_table, f, indent=2)
        print(f"[QFilter] Q-table saved → {path} ({len(self.q_table)} states)")

    def load(self, path):
        with open(path, "r") as f:
            self.q_table = json.load(f)

    # ------------------------------------------------------------------
    # Summary after full run
    # ------------------------------------------------------------------
    def print_summary(self):
        if not self.gen_stats:
            return
        total_eval  = sum(s["evaluated"] for s in self.gen_stats)
        total_skip  = sum(s["skipped"]   for s in self.gen_stats)
        total       = total_eval + total_skip
        skip_pct    = (total_skip / total * 100) if total > 0 else 0
        print("\n" + "="*60)
        print("[QFilter] Run Summary")
        print(f"  Total candidates generated : {total}")
        print(f"  Total MAESTRO calls        : {total_eval}")
        print(f"  Total skipped by Q-filter  : {total_skip}  ({skip_pct:.1f}%)")
        print(f"  Final ε                    : {self.epsilon:.4f}")
        print(f"  Unique states in Q-table   : {len(self.q_table)}")
        print("="*60)
        # Top 5 best states
        if self.q_table:
            sorted_states = sorted(self.q_table.items(), key=lambda x: x[1], reverse=True)
            print("  Top 5 genome states by Q-value:")
            for k, v in sorted_states[:5]:
                print(f"    {k:30s}  Q={v:.2f}")
        print("="*60 + "\n")