"""Record/replay: demo mode serves ONLY recorded real responses.

Key format: sha256 of canonical(model, state, questions-as-plain-dicts).
Real recordings have meta.recorded_at + latency_ms. Anything hand-made MUST
carry _origin starting with 'illustrative' and is never presented as Jev output.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC
from pathlib import Path

from .client import DecisionResult

RECORDINGS_DIR = Path(__file__).resolve().parent.parent / "recordings"


class CacheMiss(RuntimeError):
    pass


def canonical_key(model: str, state, questions: dict) -> str:
    payload = json.dumps(
        {"model": model, "state": state, "questions": _questions_to_plain(questions)},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _questions_to_plain(questions: dict) -> dict:
    out = {}
    for k, q in questions.items():
        if isinstance(q, dict):
            out[k] = q
        else:
            d = {"type": getattr(q, "type", q.__class__.__name__.lower())}
            for attr in ("instructions", "criteria"):
                if hasattr(q, attr):
                    d[attr] = getattr(q, attr)
            out[k] = d
    return out


def record_path(key: str) -> Path:
    return RECORDINGS_DIR / f"{key}.json"


def save_recording(model, state, questions: dict, result: DecisionResult, latency_ms: float,
                     retry_count: int = 0, where: str = "") -> Path:
    """Store requested_model + resolved response.model honestly (alias may move)."""
    from datetime import datetime

    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    key = canonical_key(model, state, questions)
    doc = {
        "request": {
            "requested_model": model,
            "model": model,
            "state": state,
            "questions": _questions_to_plain(questions),
        },
        "response": result.raw,  # raw["model"] is the resolved ID, e.g. jev-1.13.0
        "meta": {
            "recorded_at": datetime.now(UTC).isoformat(),
            "latency_ms": latency_ms,
            "key": key,
            "retry_count": retry_count,
            "where": where,
        },
    }
    p = record_path(key)
    p.write_text(json.dumps(doc, indent=2))
    update_manifest(p, doc, decision="kept", reason="")
    return p


def update_manifest(path: Path, doc: dict, decision: str, reason: str) -> None:
    """Manifest backs 'chosen from N' — full state/questions/result per candidate."""
    mp = RECORDINGS_DIR / "manifest.json"
    try:
        manifest = json.loads(mp.read_text()) if mp.exists() else {"candidates": []}
    except Exception:
        manifest = {"candidates": []}
    entry = {
        "file": path.name,
        "decision": decision,
        "reason": reason,
        "requested_model": doc.get("request", {}).get("requested_model"),
        "resolved_model": (doc.get("response", {}) or {}).get("model"),
        "recorded_at": doc.get("meta", {}).get("recorded_at"),
        "latency_ms": doc.get("meta", {}).get("latency_ms"),
        "state": doc.get("request", {}).get("state"),
        "questions": doc.get("request", {}).get("questions"),
        "response": doc.get("response"),
    }
    cands = [c for c in manifest.get("candidates", []) if c.get("file") != path.name]
    cands.append(entry)
    manifest["candidates"] = sorted(cands, key=lambda c: c.get("file", ""))
    manifest["n"] = len(cands)
    mp.write_text(json.dumps(manifest, indent=2))


def load_recording(model, state, questions: dict) -> DecisionResult:
    key = canonical_key(model, state, questions)
    p = record_path(key)
    if not p.exists():
        # Also search by matching request content (preset files use readable names).
        found = find_preset(model, state, questions)
        if found is None:
            raise CacheMiss(
                "No recorded response for this exact state+questions. "
                "Demo mode offers preset scenarios only — add TYPESAFE_API_KEY "
                "to try your own (live mode)."
            )
        p = found
    doc = json.loads(p.read_text())
    if str(doc.get("_origin", "")).startswith("illustrative"):
        raise CacheMiss(
            f"Recording {p.name} is illustrative, not a real Jev response. "
            "Add TYPESAFE_API_KEY and run `make record` for real data."
        )
    resp = doc["response"]
    usage = resp.get("usage", {})
    return DecisionResult(
        answers=resp.get("answers", {}),
        raw=resp,
        latency_ms=float(doc.get("meta", {}).get("latency_ms", 0.0)),
        input_tokens=int(usage.get("input_tokens", 0) or 0),
        output_tokens=int(usage.get("output_tokens", 0) or 0),
        model=str(resp.get("model", model)),
        recorded_at=str(doc.get("meta", {}).get("recorded_at", "")),
    )


def find_preset(model, state, questions: dict) -> Path | None:
    """Match readable preset files by request content (ignores filename key)."""
    if not RECORDINGS_DIR.exists():
        return None
    want_q = _questions_to_plain(questions)
    for p in RECORDINGS_DIR.glob("*.json"):
        if p.name == "manifest.json":
            continue
        try:
            doc = json.loads(p.read_text())
        except Exception:
            continue
        req = doc.get("request")
        if not req:
            continue
        if req.get("state") == state and req.get("questions") == want_q:
            return p
    return None


def list_presets() -> list[dict]:
    """Readable preset list for demo dropdown (skips illustrative files)."""
    out = []
    if not RECORDINGS_DIR.exists():
        return out
    for p in sorted(RECORDINGS_DIR.glob("*.json")):
        if p.name == "manifest.json":
            continue
        try:
            doc = json.loads(p.read_text())
        except Exception:
            continue
        if str(doc.get("_origin", "")).startswith("illustrative"):
            continue
        req = doc.get("request")
        if not req:
            continue
        out.append(
            {
                "file": p.name,
                "model": req.get("model"),
                "state_preview": str(req.get("state"))[:80],
                "questions": list((req.get("questions") or {}).keys()),
                "recorded_at": doc.get("meta", {}).get("recorded_at", ""),
            }
        )
    return out
