from jevlab.cache import CacheMiss, canonical_key
from jevlab.client import DecisionResult


def test_canonical_key_stable():
    k1 = canonical_key("m", "s", {"a": {"type": "noul", "instructions": "x"}})
    k2 = canonical_key("m", "s", {"a": {"type": "noul", "instructions": "x"}})
    assert k1 == k2


def test_demo_miss_is_friendly():
    from jevlab import cache

    try:
        cache.load_recording("jev-latest", "never-recorded-state-xyz", {"q": {"type": "noul", "instructions": "x"}})
    except CacheMiss as e:
        assert "preset scenarios only" in str(e)
    else:
        raise AssertionError("expected CacheMiss")


def test_result_dataclass():
    r = DecisionResult(answers={}, raw={}, latency_ms=1.0, input_tokens=5, output_tokens=0, model="m")
    assert r.input_tokens == 5
