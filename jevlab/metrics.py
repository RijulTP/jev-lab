"""Calibration helpers. NEVER pool Choice/Score confidence with Noul proxy.

Score "accuracy" definitions (see README "How we score Score"):
- PRIMARY p_true: probability assigned to the labeled level (calibration quantity).
- MAE: |score - true_level| in levels (ordinal, fractional-aware).
- within_one: 1 if |score - true_level| < 1.0 else 0 (tolerant secondary).
Choice: p_max vs accuracy AND confidence vs accuracy plotted separately.
Noul: binned P(yes) vs observed frequency.
5 bins default (n~150 -> ~30/bin), Wilson 95% CI, per-bin counts.
"""
from __future__ import annotations

import math


def wilson_ci(hits: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = hits / n
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (center - margin) / denom), min(1.0, (center + margin) / denom))


def reliability_bins(pairs: list[tuple[float, int]], n_bins: int = 5) -> list[dict]:
    """pairs: (predicted_prob_or_confidence, correct_0/1). Returns per-bin stats."""
    bins = []
    for b in range(n_bins):
        lo, hi = b / n_bins, (b + 1) / n_bins
        in_bin = [(p, y) for p, y in pairs if (p >= lo and (p < hi or (b == n_bins - 1 and p <= hi)))]
        n = len(in_bin)
        if n:
            mean_p = sum(p for p, _ in in_bin) / n
            acc = sum(y for _, y in in_bin) / n
            lo_ci, hi_ci = wilson_ci(sum(y for _, y in in_bin), n)
        else:
            mean_p, acc, lo_ci, hi_ci = (lo + hi) / 2, 0.0, 0.0, 1.0
        bins.append(
            {"bin": b, "lo": lo, "hi": hi, "n": n,
             "mean_pred": mean_p, "accuracy": acc, "ci_lo": lo_ci, "ci_hi": hi_ci}
        )
    return bins


def ece(pairs: list[tuple[float, int]], n_bins: int = 5) -> float:
    bins = reliability_bins(pairs, n_bins)
    n = max(1, sum(b["n"] for b in bins))
    return sum(b["n"] / n * abs(b["accuracy"] - b["mean_pred"]) for b in bins)


def score_p_true(probabilities: dict, true_level: int) -> float:
    return float(probabilities.get(str(true_level), probabilities.get(true_level, 0.0)) or 0.0)


def score_mae(score: float, true_level: int) -> float:
    return abs(float(score) - float(true_level))


def score_within_one(score: float, true_level: int) -> int:
    return 1 if abs(float(score) - float(true_level)) < 1.0 else 0
