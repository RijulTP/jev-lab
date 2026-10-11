from jevlab.client import noul_confidence_proxy
from jevlab.gates import route_answer, route_noul
from jevlab.metrics import (
    ece,
    reliability_bins,
    score_mae,
    score_p_true,
    score_within_one,
    wilson_ci,
)


def test_noul_proxy_is_ours():
    assert noul_confidence_proxy(1.0) == 1.0
    assert noul_confidence_proxy(0.5) == 0.0
    assert noul_confidence_proxy(0.0) == 1.0


def test_gates_choice():
    assert route_answer({"type": "choice", "confidence": 0.9}) == "auto-act"
    assert route_answer({"type": "choice", "confidence": 0.6}) == "human-review"
    assert route_answer({"type": "choice", "confidence": 0.1}) == "escalate"


def test_noul_gates_on_p_directly():
    assert route_noul(0.9) == "act-yes"
    assert route_noul(0.1) == "act-no"
    assert route_noul(0.5) == "human-review"


def test_reliability_bins_counts_and_ci():
    pairs = [(0.9, 1)] * 20 + [(0.9, 0)] * 10 + [(0.2, 0)] * 20
    bins = reliability_bins(pairs, n_bins=5)
    assert len(bins) == 5
    assert sum(b["n"] for b in bins) == len(pairs)
    for b in bins:
        assert b["ci_lo"] <= b["accuracy"] <= b["ci_hi"]
    assert 0.0 <= ece(pairs) <= 1.0
    lo, hi = wilson_ci(0, 0)
    assert (lo, hi) == (0.0, 1.0)


def test_score_accuracy_defs():
    probs = {"0": 0.0, "1": 0.57, "2": 0.43}
    assert abs(score_p_true(probs, 1) - 0.57) < 1e-9
    assert abs(score_mae(1.43, 1) - 0.43) < 1e-9
    assert score_within_one(1.43, 1) == 1
    assert score_within_one(2.0, 0) == 0
