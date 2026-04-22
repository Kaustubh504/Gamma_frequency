"""
q_filter.py
============
Q-Learning filter for GAMMA's genetic algorithm.

Maintains separate Q-tables for evaluation, crossover, growth, and aging phases.
Uses dynamic table sizing (OrderedDict as LRU cache) and parameterized alpha/gamma.
"""

import random
import json
import math
import os
from collections import OrderedDict

class QFilter:
    def __init__(
        self,
        alpha=0.1,              # learning rate
        gamma_param=0.9,        # Discount factor (gamma)
        table_size=10000,       # Maximum size of each Q-table
        epsilon=1.0,            # initial exploration rate (1.0 = explore everything at first)
        epsilon_decay=0.9,      # multiply epsilon by this after each generation
        epsilon_min=0.10,       # floor for epsilon (never go fully greedy)
        skip_threshold=0.0,     # Q(s,1) must exceed this to evaluate/proceed
        q_table_path=None,      # optional path to save/load Q-table across runs
        auto_threshold=True,    # auto-tune skip_threshold from gen-1 rewards
        threshold_percentile=25,# skip genomes below this reward percentile
    ):
        self.alpha = alpha
        self.gamma_param = gamma_param
        self.table_size = table_size
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        self.skip_threshold = skip_threshold
        self.q_table_path = q_table_path
        self.auto_threshold = auto_threshold
        self.threshold_percentile = threshold_percentile
        self._reward_buffer = []       # collects gen-1 rewards for calibration
        self._threshold_calibrated = False

        # Separate tables for different phases using OrderedDict for sizing
        self.q_table_eval = OrderedDict()
        self.q_table_cross = OrderedDict()
        self.q_table_growth = OrderedDict()
        self.q_table_aging = OrderedDict()

        # Stats per generation for logging
        self.gen_stats = []

        if q_table_path and os.path.exists(q_table_path):
            self.load(q_table_path)
            print(f"[QFilter] Loaded Q-tables from {q_table_path}")

    # ------------------------------------------------------------------
    # State extraction
    # ------------------------------------------------------------------
    @staticmethod
    def _tile_bucket(size):
        """Log2-bin a tile size into 8 buckets (0=1, 1=2-3, 2=4-7, ..., 7=128+)."""
        try:
            s = int(size)
        except (TypeError, ValueError):
            return 0
        if s <= 1:
            return 0
        return min(int(math.log2(s)), 7)

    def extract_state(self, indv):
        """
        Extract a hashable state from a genome individual.
        State = sp_dim | loop_order | tile_bins
        Tile sizes are log2-bucketed to keep state space tractable while
        capturing memory access patterns that loop_order alone misses.
        """
        if len(indv) < 7:
            return "UNKNOWN|()|0,0,0,0,0,0"
        sp_dim     = indv[0][0]
        loop_order = "".join(indv[i][0] for i in range(1, 7))
        tile_bins  = ",".join(str(self._tile_bucket(indv[i][1])) for i in range(1, 7))
        return f"{sp_dim}|{loop_order}|{tile_bins}"

    # ------------------------------------------------------------------
    # Core Q-table operations
    # ------------------------------------------------------------------
    def _enforce_table_size(self, table):
        """Maintains dynamic table size by popping oldest items if exceeded."""
        while len(table) > self.table_size:
            table.popitem(last=False)

    def get_q_value(self, state_key, table_type="eval"):
        """Return Q(s, action=1) for a specific phase."""
        table = getattr(self, f"q_table_{table_type}")
        return table.get(state_key, 0.0)

    def update(self, state_key, reward, next_state_key=None, table_type="eval"):
        """
        Updates the specified Q-table using the Q-learning equation.
        Q(s,a) = Q(s,a) + alpha * (R + gamma * max(Q(s',a)) - Q(s,a))
        """
        # Buffer valid rewards from gen-1 eval phase for auto-threshold calibration
        if (self.auto_threshold and not self._threshold_calibrated
                and table_type == "eval"
                and reward is not None and reward > -1e15):
            self._reward_buffer.append(reward)

        table = getattr(self, f"q_table_{table_type}")
        old_q = table.get(state_key, 0.0)
        next_q = table.get(next_state_key, 0.0) if next_state_key else 0.0
        new_q = old_q + self.alpha * (reward + (self.gamma_param * next_q) - old_q)

        if state_key in table:
            del table[state_key]
        table[state_key] = new_q
        self._enforce_table_size(table)

    def _calibrate_threshold(self):
        """Set skip_threshold to threshold_percentile of gen-1 observed rewards."""
        if not self._reward_buffer:
            print("[QFilter] Auto-threshold: no rewards collected, keeping default.")
            self._threshold_calibrated = True
            return
        rewards = sorted(self._reward_buffer)
        idx = max(0, int(len(rewards) * self.threshold_percentile / 100) - 1)
        self.skip_threshold = rewards[idx]
        self._threshold_calibrated = True
        print(f"[QFilter] Auto-threshold set: {self.skip_threshold:.3e} "
              f"(p{self.threshold_percentile} of {len(rewards)} gen-1 rewards; "
              f"range [{rewards[0]:.2e}, {rewards[-1]:.2e}])")

    # ------------------------------------------------------------------
    # Decision: should we proceed with this operation?
    # ------------------------------------------------------------------
    def should_proceed(self, indv, table_type="eval"):
        """
        ε-greedy decision for a candidate genome for a specific phase.
        Returns: True to execute the phase, False to skip.
        """
        if random.random() < self.epsilon:
            return True   # explore

        state_key = self.extract_state(indv)
        q_val = self.get_q_value(state_key, table_type)
        return q_val > self.skip_threshold   # exploit Q-table

    def should_evaluate(self, indv):
        """Alias for backward compatibility with the main evaluation loop."""
        return self.should_proceed(indv, table_type="eval")

    # ------------------------------------------------------------------
    # After each generation: decay epsilon, log stats
    # ------------------------------------------------------------------
    def end_of_generation(self, gen, n_evaluated, n_skipped):
        """Decays epsilon, auto-calibrates threshold after gen 1, logs stats."""
        # Calibrate skip_threshold from gen-1 rewards before filter starts exploiting
        if self.auto_threshold and not self._threshold_calibrated and gen == 0:
            self._calibrate_threshold()

        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
        stat = {
            "gen":        gen + 1,
            "evaluated":  n_evaluated,
            "skipped":    n_skipped,
            "epsilon":    round(self.epsilon, 4),
            "q_states":   len(self.q_table_eval), 
        }
        self.gen_stats.append(stat)
        print(
            f"[QFilter] Gen {gen+1}: evaluated={n_evaluated}, skipped={n_skipped}, "
            f"ε={self.epsilon:.3f}, Eval Q-states={len(self.q_table_eval)}"
        )

    # ------------------------------------------------------------------
    # Save / load Q-table across runs (warm-starting)
    # ------------------------------------------------------------------
    def save(self, path=None):
        path = path or self.q_table_path
        if path is None:
            return
        
        # Combine all tables for saving into one JSON
        save_data = {
            "eval": list(self.q_table_eval.items()),
            "cross": list(self.q_table_cross.items()),
            "growth": list(self.q_table_growth.items()),
            "aging": list(self.q_table_aging.items())
        }
        
        with open(path, "w") as f:
            json.dump(save_data, f, indent=2)
        print(f"[QFilter] Q-tables saved → {path} (Eval states: {len(self.q_table_eval)})")

    def load(self, path):
        with open(path, "r") as f:
            save_data = json.load(f)
            
        # Handle old format (single dict) vs new format (dict of dicts) gracefully
        if "eval" in save_data:
            self.q_table_eval = OrderedDict(save_data.get("eval", []))
            self.q_table_cross = OrderedDict(save_data.get("cross", []))
            self.q_table_growth = OrderedDict(save_data.get("growth", []))
            self.q_table_aging = OrderedDict(save_data.get("aging", []))
        else:
            # Legacy load for older JSON files
            self.q_table_eval = OrderedDict(save_data.items())

    # ------------------------------------------------------------------
    # Q-value whitelist helpers (used by guided mutation in gamma.py)
    # ------------------------------------------------------------------
    def get_good_states(self, table_type="eval", top_n=20):
        """
        Returns top_n highest Q-value state keys from the specified table.
        State format: "sp_dim|loop_order"  e.g. "K|KCYRXS"
        Returns list of (state_key, q_value) tuples sorted descending.
        """
        table = getattr(self, f"q_table_{table_type}")
        if not table:
            return []
        sorted_states = sorted(table.items(), key=lambda x: x[1], reverse=True)
        return sorted_states[:top_n]

    def get_good_loop_orders(self, table_type="eval", top_n=30, threshold=0.0):
        """
        Returns a set of (sp_dim, loop_order_tuple) pairs from the top Q-states.
        Used by gamma.py to identify which genome structures to protect from
        structural mutation (sp_dim swaps). Only returns states with Q > threshold.

        Example return value:
            {("K", ("K","C","Y","R","X","S")), ("C", ("C","K","X","Y","R","S")), ...}
        """
        good = set()
        for state_key, q_val in self.get_good_states(table_type, top_n):
            if q_val <= threshold:
                continue
            parts = state_key.split("|")
            if len(parts) >= 2 and len(parts[1]) == 6:
                sp_dim = parts[0]
                loop_order = tuple(parts[1])   # e.g. ('K','C','Y','R','X','S')
                good.add((sp_dim, loop_order))
        return good

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
        print(f"  Eval States Known          : {len(self.q_table_eval)}")
        print(f"  Crossover States Known     : {len(self.q_table_cross)}")
        print(f"  Growth States Known        : {len(self.q_table_growth)}")
        print(f"  Aging States Known         : {len(self.q_table_aging)}")
        print("="*60)
        
        # Top 5 best states in Eval table
        if self.q_table_eval:
            sorted_states = sorted(self.q_table_eval.items(), key=lambda x: x[1], reverse=True)
            print("  Top 5 genome states by Q-value (Eval Phase):")
            for k, v in sorted_states[:5]:
                print(f"    {k:30s}  Q={v:.2f}")
        print("="*60 + "\n")