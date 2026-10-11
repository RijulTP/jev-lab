"""Thin wrapper so the UI never touches typesafe_sdk directly."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass


@dataclass
class DecisionResult:
    answers: dict
    raw: dict
    latency_ms: float
    input_tokens: int
    output_tokens: int
    model: str
    recorded_at: str | None = None  # set when served from replay


def _answer_to_dict(name: str, ans) -> dict:
    """Normalize SDK typed answers (or plain dicts) to plain dicts."""
    if isinstance(ans, dict):
        return {"name": name, **ans}
    atype = getattr(ans, "type", None) or ans.__class__.__name__.lower()
    d: dict = {"name": name, "type": atype}
    for k in ("choice", "score", "noul", "confidence", "probabilities", "legend"):
        if hasattr(ans, k):
            v = getattr(ans, k)
            d[k] = dict(v) if isinstance(v, dict) else v
    return d


def _response_to_raw(response) -> dict:
    answers: dict = {}
    raw_answers = getattr(response, "answers", None) or {}
    # SDK also exposes .choices/.scores/.nouls; .answers covers all.
    if isinstance(raw_answers, dict):
        for name, ans in raw_answers.items():
            answers[name] = _answer_to_dict(name, ans)
    usage = getattr(response, "usage", None)
    if usage is None:
        usage = {"input_tokens": 0, "output_tokens": 0}
    elif not isinstance(usage, dict):
        usage = {
            "input_tokens": getattr(usage, "input_tokens", 0) or 0,
            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
        }
    return {
        "model": getattr(response, "model", os.getenv("JEV_MODEL", "jev-latest")),
        "answers": answers,
        "usage": usage,
    }


class JevError(RuntimeError):
    pass


def decide(state, questions: dict, model: str | None = None, command: str = "decide",
           max_retries: int = 1) -> DecisionResult:
    """Live call with $1 hard budget guardrail. Raises JevError/BudgetExceeded."""
    from .budget import BudgetExceeded, estimate_tokens, observe, release, reserve, settle

    api_key = os.getenv("TYPESAFE_API_KEY", "")
    if not api_key:
        raise JevError(
            "Missing TYPESAFE_API_KEY. Add it to .env (see .env.example) "
            "or run in demo mode with recorded presets."
        )
    model = model or os.getenv("JEV_MODEL", "jev-latest")
    try:
        from typesafe_sdk import RetryPolicy, TypeSafeClient
    except ImportError as e:
        raise JevError(f"typesafe-sdk not installed. Run `make setup`. ({e})")

    import json as _json

    chars = len(_json.dumps({"state": state, "questions": questions}, default=str))
    estimate = estimate_tokens(state, questions)
    reserve(estimate)  # fail-closed ledger + hard block + per-request ceiling
    retries = 0
    # Own retry loop (SDK internal retries disabled) so each attempt preflights.
    while True:
        try:
            t0 = time.perf_counter()
            try:
                with TypeSafeClient(retry=RetryPolicy(max_retries=0)) as client:
                    response = client.system_one(state=state, questions=questions, model=model)
            except TypeError:
                # Older SDK without retry kwarg: fall back (internal retries may apply;
                # reservation covers the attempt; retry_count logged by caller).
                with TypeSafeClient() as client:
                    response = client.system_one(state=state, questions=questions, model=model)
        except BudgetExceeded:
            release(estimate)
            raise
        except TimeoutError as e:
            # Possibly billed server-side: count at estimate until reconciled.
            settle(estimate, 0, command=command, timeout_billed=True)
            raise JevError(f"Jev call timed out (counted at estimate {estimate} tok, possibly billed): {e}")
        except Exception as e:
            msg = str(e)
            if "429" in msg and retries < max_retries:
                retries += 1
                reserve(estimate)  # preflight the retry too
                release(estimate)  # release previous attempt's duplicate hold once
                # Re-reserve once net: keep single estimate held across retry.
                # (reserve then release ordering above nets +0; settle below commits actual.)
                import time as _t

                _t.sleep(0.5 * retries)
                continue
            if "429" in msg:
                release(estimate)
                raise JevError(
                    "Rate limited (HTTP 429). Back off, lower concurrency, "
                    "and honor retry-after. Limits change dynamically; see `make doctor`."
                )
            if "413" in msg or "context" in msg.lower() or "too large" in msg.lower():
                release(estimate)
                raise JevError(f"State too large for context window (64k total / 32k state+longest Q). ({msg})")
            release(estimate)
            raise JevError(f"Jev call failed: {msg}")
        latency_ms = (time.perf_counter() - t0) * 1000.0
        raw = _response_to_raw(response)
        usage = raw.get("usage", {})
        actual = int(usage.get("input_tokens", 0) or 0)
        settle(estimate, actual, command=command)
        observe(chars, actual)
        return DecisionResult(
            answers=raw["answers"],
            raw=raw,
            latency_ms=latency_ms,
            input_tokens=actual,
            output_tokens=int(usage.get("output_tokens", 0) or 0),
            model=str(raw.get("model", model)),
        )


def noul_confidence_proxy(noul_p: float) -> float:
    """OUR proxy, not a Jev field. Docs suggest |2p-1| as opt-in gating helper.

    Noul has no separate confidence; the probability IS the uncertainty.
    Use only for gating convenience, never pooled with Choice/Score confidence.
    """
    return abs(2.0 * float(noul_p) - 1.0)
