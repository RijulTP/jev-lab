"""$1 hard budget guardrail. Single choke point for all live calls.

Spend is counted from ACTUAL usage.input_tokens post-call; pre-call estimates
(overhead + chars/4, converging on max observed ratio) are for reservation only.
Fail closed: corrupt/unreadable ledger blocks live calls, never resets to zero.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from contextlib import contextmanager
from datetime import UTC
from pathlib import Path

from .config import load_limits

_THREAD_LOCK = threading.Lock()


class BudgetExceeded(RuntimeError):
    pass


class LedgerError(RuntimeError):
    pass


def _paths() -> Path:
    lim = load_limits()
    name = os.getenv("JEV_BUDGET_LEDGER", str(lim.get("budget_ledger_path", ".jevlab_usage.json")))
    p = Path(name)
    return p if p.is_absolute() else Path(__file__).resolve().parent.parent / p


def cap_usd() -> float:
    if os.getenv("JEV_BUDGET_CAP_USD"):
        return float(os.getenv("JEV_BUDGET_CAP_USD", "1.0"))
    return float(load_limits().get("budget_cap_usd", 1.0))


def price_per_mtok() -> float:
    return float(load_limits().get("price_input_per_mtok_usd", 0.042))


def tokens_to_usd(n: int) -> float:
    return n / 1_000_000 * price_per_mtok()


@contextmanager
def _file_locked(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix(path.suffix + ".lock"), "w") as fh:
        try:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass  # Windows / no fcntl: thread lock still protects in-process
        yield
        try:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except (ImportError, OSError):
            pass


def _read_ledger(path: Path) -> dict:
    if not path.exists():
        return {"spent_tokens": 0, "calls": 0, "by_command": {},
                "max_ratio": 0.25, "reserved_tokens": 0}
    try:
        doc = json.loads(path.read_text())
    except Exception as e:
        raise LedgerError(
            f"Budget ledger {path} unreadable/corrupt — blocking live calls (fail closed). "
            f"Inspect or archive it; never auto-resets. ({e})"
        )
    for k in ("spent_tokens", "reserved_tokens"):
        if not isinstance(doc.get(k, 0), (int, float)):
            raise LedgerError(f"Budget ledger {path} corrupt field {k!r} — blocking live calls.")
    doc.setdefault("calls", 0)
    doc.setdefault("by_command", {})
    doc.setdefault("max_ratio", 0.25)
    return doc


def _write_ledger_atomic(path: Path, doc: dict) -> None:
    with tempfile.NamedTemporaryFile("w", dir=str(path.parent), delete=False) as f:
        json.dump(doc, f, indent=2)
        tmpname = f.name
    os.replace(tmpname, path)


def estimate_tokens(state, questions: dict) -> int:
    """Over-estimating pre-call estimator: overhead + chars*ratio (max observed)."""
    lim = load_limits()
    overhead = int(lim.get("budget_overhead_tokens", 350))
    try:
        ratio = max(0.25, float(_read_ledger(_paths()).get("max_ratio", 0.25)))
    except LedgerError:
        ratio = 0.25
    chars = len(json.dumps({"state": state, "questions": questions}, default=str))
    return overhead + int(chars * ratio + chars * 0.10)  # +10% margin


def status() -> dict:
    path = _paths()
    try:
        doc = _read_ledger(path)
    except LedgerError as e:
        return {"error": str(e), "cap_usd": cap_usd()}
    spent_usd = tokens_to_usd(int(doc.get("spent_tokens", 0)))
    cap = cap_usd()
    return {"spent_tokens": int(doc.get("spent_tokens", 0)),
            "reserved_tokens": int(doc.get("reserved_tokens", 0)),
            "spent_usd": spent_usd, "cap_usd": cap,
            "remaining_usd": cap - spent_usd,
            "calls": doc.get("calls", 0), "warn_at_80": spent_usd >= 0.8 * cap}


def reserve(estimate: int) -> None:
    """Reserve under locks; raises BudgetExceeded (hard block) or LedgerError."""
    lim = load_limits()
    ceiling = int(lim.get("budget_per_request_ceiling_tokens", 64000))
    if estimate > ceiling:
        raise BudgetExceeded(
            f"Single-request estimate {estimate} tok exceeds per-request ceiling "
            f"{ceiling} tok — blocked regardless of budget (likely huge-state bug)."
        )
    path = _paths()
    with _THREAD_LOCK, _file_locked(path):
        doc = _read_ledger(path)  # fail closed here
        spent_usd = tokens_to_usd(int(doc["spent_tokens"]) + int(doc["reserved_tokens"]) + estimate)
        if spent_usd > cap_usd():
            raise BudgetExceeded(
                f"Budget cap ${cap_usd():.2f} would be exceeded "
                f"(spent ${tokens_to_usd(int(doc['spent_tokens'])):.4f} + "
                f"reserved {int(doc['reserved_tokens'])} tok + estimate {estimate} tok). Blocked."
            )
        doc["reserved_tokens"] = int(doc["reserved_tokens"]) + estimate
        _write_ledger_atomic(path, doc)


def settle(estimate: int, actual: int, command: str = "", timeout_billed: bool = False) -> None:
    """Replace reservation with actual usage (or estimate on timeout — possibly billed)."""
    path = _paths()
    billed = estimate if timeout_billed else int(actual or 0)
    with _THREAD_LOCK, _file_locked(path):
        doc = _read_ledger(path)
        doc["reserved_tokens"] = max(0, int(doc["reserved_tokens"]) - estimate)
        doc["spent_tokens"] = int(doc["spent_tokens"]) + billed
        doc["calls"] = int(doc.get("calls", 0)) + 1
        if command:
            doc["by_command"][command] = int(doc["by_command"].get(command, 0)) + billed
        # Converge estimator upward only: track max actual/chars ratio.
        # Caller passes chars via actual>=0; ratio update happens in observe().
        _write_ledger_atomic(path, doc)


def release(estimate: int) -> None:
    path = _paths()
    with _THREAD_LOCK, _file_locked(path):
        doc = _read_ledger(path)
        doc["reserved_tokens"] = max(0, int(doc["reserved_tokens"]) - estimate)
        _write_ledger_atomic(path, doc)


def observe(chars: int, actual: int) -> None:
    """Track max observed tokens/char so the estimator converges on reality."""
    if chars <= 0 or actual <= 0:
        return
    path = _paths()
    with _THREAD_LOCK, _file_locked(path):
        try:
            doc = _read_ledger(path)
        except LedgerError:
            return
        doc["max_ratio"] = max(float(doc.get("max_ratio", 0.25)), actual / chars)
        _write_ledger_atomic(path, doc)


def reset_archive() -> Path:
    """Archive (never wipe): rename ledger with timestamp, start fresh."""
    from datetime import datetime

    path = _paths()
    if path.exists():
        dest = path.with_name(f"{path.stem}.{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json")
        path.rename(dest)
        return dest
    return path
