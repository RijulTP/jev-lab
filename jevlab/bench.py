"""Benchmark math: warm-up exclusion, interleaved runs, median + min-max.

Importable/testable; scripts/bench.py is the thin CLI.
"""
from __future__ import annotations

import statistics


def summarize(runs: list[float]) -> dict:
    """Median + min-max over non-empty runs (warm-up already excluded by caller)."""
    if not runs:
        return {"n": 0, "median_ms": 0.0, "min_ms": 0.0, "max_ms": 0.0}
    return {"n": len(runs), "median_ms": float(statistics.median(runs)),
            "min_ms": float(min(runs)), "max_ms": float(max(runs))}


def interleave(methods: list[str], n_runs: int) -> list[str]:
    """Round-robin ordering to avoid ordering bias: A B C A B C ..."""
    order = []
    for _ in range(n_runs):
        order.extend(methods)
    return order


def drop_warmup(runs: list[float]) -> list[float]:
    return runs[1:] if len(runs) > 1 else runs
