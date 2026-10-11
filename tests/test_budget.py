"""Budget guardrail tests: estimator, reservation races, fail-closed ledger, replay purity."""
import json
import threading

import pytest

from jevlab import budget
from jevlab.budget import BudgetExceeded, LedgerError


def _small_request():
    # Mirrors docs quickstart shape: 46-char state + 1 short question -> ~392 tok actual.
    state = "x" * 46
    questions = {"urgency": {"type": "noul", "instructions": "Does this express urgency?"}}
    return state, questions


def test_small_request_never_underestimates(tmp_path, monkeypatch):
    monkeypatch.setenv("JEV_BUDGET_LEDGER", str(tmp_path / "u.json"))
    state, questions = _small_request()
    est = budget.estimate_tokens(state, questions)
    assert est >= 392, f"estimator {est} under-counts documented 392-token call"


def test_parallel_reservation_never_exceeds_cap(tmp_path, monkeypatch):
    monkeypatch.setenv("JEV_BUDGET_LEDGER", str(tmp_path / "u.json"))
    monkeypatch.setenv("JEV_BUDGET_CAP_USD", "0.001")  # ~23.8k tok
    est = 5000
    allowed, blocked = [], []

    def worker():
        try:
            budget.reserve(est)
            allowed.append(1)
        except BudgetExceeded:
            blocked.append(1)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    # cap ~23.8k: at most 4 x 5k reservations may pass
    assert len(allowed) <= 4 and blocked
    st = budget.status()
    assert st["spent_tokens"] + st["reserved_tokens"] <= 25000


def test_corrupt_ledger_blocks_not_resets(tmp_path, monkeypatch):
    p = tmp_path / "u.json"
    p.write_text("{corrupt")
    monkeypatch.setenv("JEV_BUDGET_LEDGER", str(p))
    with pytest.raises(LedgerError):
        budget.reserve(100)
    st = budget.status()
    assert "error" in st


def test_failed_call_releases_reservation(tmp_path, monkeypatch):
    monkeypatch.setenv("JEV_BUDGET_LEDGER", str(tmp_path / "u.json"))
    est = 1000
    budget.reserve(est)
    assert budget.status()["reserved_tokens"] == est
    budget.release(est)
    assert budget.status()["reserved_tokens"] == 0


def test_timeout_counted_at_estimate(tmp_path, monkeypatch):
    monkeypatch.setenv("JEV_BUDGET_LEDGER", str(tmp_path / "u.json"))
    est = 1000
    budget.reserve(est)
    budget.settle(est, 0, command="t", timeout_billed=True)
    assert budget.status()["spent_tokens"] == est


def test_per_request_ceiling(tmp_path, monkeypatch):
    monkeypatch.setenv("JEV_BUDGET_LEDGER", str(tmp_path / "u.json"))
    with pytest.raises(BudgetExceeded):
        budget.reserve(65000)


def test_replay_never_touches_ledger(tmp_path, monkeypatch):
    from jevlab import cache

    lp = tmp_path / "u.json"
    monkeypatch.setenv("JEV_BUDGET_LEDGER", str(lp))
    before = lp.read_text() if lp.exists() else None
    try:
        cache.load_recording("jev-latest", "never-recorded-xyz", {"q": {"type": "noul", "instructions": "x"}})
    except Exception:  # noqa: S110 — any miss error is fine; point is ledger untouched
        pass
    after = lp.read_text() if lp.exists() else None
    assert before == after


def test_reset_archives_not_wipes(tmp_path, monkeypatch):
    lp = tmp_path / "u.json"
    lp.write_text(json.dumps({"spent_tokens": 5, "calls": 1, "by_command": {}, "max_ratio": 0.25, "reserved_tokens": 0}))
    monkeypatch.setenv("JEV_BUDGET_LEDGER", str(lp))
    dest = budget.reset_archive()
    assert dest != lp and dest.exists()
    assert budget.status()["spent_tokens"] == 0
