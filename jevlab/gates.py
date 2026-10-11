"""Confidence-threshold routing.

Choice/Score gate on derived `confidence` (own thresholds).
Noul gates on P(yes) directly: yes above t_yes, no below t_no, review between.
|2p-1| proxy shown for reference only, never as the gating scale.
"""
from __future__ import annotations

from .client import noul_confidence_proxy

AUTO = "auto-act"
REVIEW = "human-review"
ESCALATE = "escalate"
YES = "act-yes"
NO = "act-no"


def route_answer(answer: dict, t_hi: float = 0.8, t_lo: float = 0.5) -> str:
    """Choice/Score path (kept for compat). Do NOT pass Noul answers here."""
    atype = (answer.get("type") or "").lower()
    if atype == "noul":
        raise ValueError("Use route_noul() for Noul answers (P(yes) thresholds).")
    conf = float(answer.get("confidence", 0.0))
    if conf >= t_hi:
        return AUTO
    if conf >= t_lo:
        return REVIEW
    return ESCALATE


def route_noul(noul_p: float, t_yes: float = 0.75, t_no: float = 0.25) -> str:
    p = float(noul_p)
    if p >= t_yes:
        return YES
    if p <= t_no:
        return NO
    return REVIEW


def noul_proxy_for_display(noul_p: float) -> float:
    return noul_confidence_proxy(noul_p)
