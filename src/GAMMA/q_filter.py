"""
q_filter.py
============
Q-Learning filter for GAMMA's genetic algorithm.

Maintains separate Q-tables for evaluation, crossover, growth, and aging phases.
Uses dynamic table sizing (OrderedDict as LRU cache) and parameterized alpha/gamma.
"""

import random
import json
import os
from collections import OrderedDict

class QFilter:
    def __init__(
        self,
        alpha=0.1,          # learning rate
        gamma_param=0.9,    # Discount factor (gamma)
        table_size=10000,   # Maximum size of each Q-table
        epsilon=1.0,        # initial exploration rate (1.0 = explore everything at first)
        epsilon_decay=0.9,  # multiply epsilon by this after each generation
        epsilon_min=0.10,   # floor for epsilon (never go fully greedy)
        skip_threshold=0.0, # Q(s,1) must exceed this to evaluate/proceed
        q_table_path=None,  # optional path to save/load Q-table across runs
        
    ):
        self.alpha = alpha
        self.gamma_param = gamma_param
        self.table_size = table_size
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        self.skip_threshold = skip_threshold
        self.q_table_path = q_table_path
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
    def extract_state(self, indv):
        """
        Extract a compact hashable state from a genome individual.
        State = sp_dim|loop_order
        """
        if len(indv) < 7:
            return "UNKNOWN|()"
        sp_dim = indv[0][0]                          
        loop_order = tuple(indv[i][0] for i in range(1, 7)) 
        return f"{sp_dim}|{''.join(loop_order)}"

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
        table = getattr(self, f"q_table_{table_type}")
        old_q = table.get(state_key, 0.0)
        
        # Calculate max Q value for next state if it exists
        next_q = table.get(next_state_key, 0.0) if next_state_key else 0.0
        
        # Apply standard Q-Learning formula
        new_q = old_q + self.alpha * (reward + (self.gamma_param * next_q) - old_q)
        
        # Update table and mark as recently used (for LRU behavior)
        table[state_key] = new_q
        table.move_to_end(state_key)
        
        self._enforce_table_size(table)

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
        """Decays epsilon and logs stats at the end of the generation."""
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