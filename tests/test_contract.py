"""Contract test: real recorded responses must match the documented schema.

Runs in CI on committed recordings only (no key). Skips visibly when only
illustrative samples exist; normal flow is `make record && make test`.
"""
import json
from pathlib import Path


def _real_recordings():
    rec = Path(__file__).resolve().parent.parent / "recordings"
    out = []
    for p in rec.glob("*.json"):
        if p.name == "manifest.json":
            continue
        try:
            doc = json.loads(p.read_text())
        except Exception:
            continue
        if str(doc.get("_origin", "")).startswith("illustrative"):
            continue
        if "request" in doc and "response" in doc:
            out.append((p, doc))
    return out


def test_contract_documented():
    """Documented behavior: MUST pass. Includes prob-sum ±0.01 and legend-derived Score bounds."""
    reals = _real_recordings()
    if not reals:
        import pytest

        pytest.skip("SKIP: no real recordings — run `make record` with TYPESAFE_API_KEY, then `make test`.")
    for p, doc in reals:
        resp = doc["response"]
        assert "model" in resp, p.name
        assert "answers" in resp and isinstance(resp["answers"], dict), p.name
        assert "usage" in resp and resp["usage"].get("input_tokens", 0) > 0, f"{p.name}: input_tokens>0"
        for name, ans in resp["answers"].items():
            assert "type" in ans, f"{p.name}:{name}"
            t = ans["type"]
            probs = ans.get("probabilities", {})
            if t == "choice":
                assert "choice" in ans and "confidence" in ans
                assert 0.0 <= ans["confidence"] <= 1.0
                assert ans["choice"] in probs, f"{p.name}:{name} choice not in probabilities"
                assert abs(sum(probs.values()) - 1.0) <= 0.01, f"{p.name}:{name} probs sum != 1"
            elif t == "score":
                assert "score" in ans and "confidence" in ans and "legend" in ans
                assert 0.0 <= ans["confidence"] <= 1.0
                levels = sorted(int(k) for k in ans["legend"])
                assert min(levels) - 1e-9 <= ans["score"] <= max(levels) + 1e-9, \
                    f"{p.name}:{name} score outside legend bounds"
                assert {str(k) for k in levels} == set(probs.keys()), f"{p.name}:{name} legend/prob keys"
                assert abs(sum(probs.values()) - 1.0) <= 0.01, f"{p.name}:{name} probs sum != 1"
            elif t == "noul":
                assert "noul" in ans and "confidence" not in ans, f"{p.name}:{name} Noul must not carry confidence"
                assert 0.0 <= ans["noul"] <= 1.0
            else:
                raise AssertionError(f"{p.name}:{name} unknown type {t}")
        blob = json.dumps(doc)
        for secret in ("sk-", "Bearer ", "TYPESAFE_API_KEY"):
            assert secret not in blob, f"{p.name} may contain a secret"
        # Alias honesty: resolved model recorded
        assert doc["response"].get("model"), f"{p.name}: missing resolved model"
