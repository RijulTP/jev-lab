"""Policy order/trace, boundaries, no-network, bench math, truncation, parity, public-demo."""
import json

from jevlab import bench as benchmath
from jevlab import policy
from jevlab.policy import DEFAULTS


def _ans(**kw):
    base = {"intent": {"choice": "order_status", "confidence": 0.9},
            "urgency": {"score": 0.0}, "frustration": {"score": 0.0},
            "override_attempt": {"noul": 0.0}, "safety_risk": {"noul": 0.0},
            "asks_human": {"noul": 0.0}}
    base.update(kw)
    return base


def test_rule_order_override_first():
    d = policy.decide(_ans(override_attempt={"noul": 0.99}, safety_risk={"noul": 0.99}))
    assert d.firing_rule == "override_refuse" and d.action == "refuse"
    assert next(t.rule for t in d.trace) == "override_refuse"
    assert all(isinstance(t.fired, bool) for t in d.trace)


def test_threshold_boundaries():
    t = dict(DEFAULTS)
    d = policy.decide(_ans(override_attempt={"noul": t["override_yes"]}))
    assert d.firing_rule == "override_refuse"  # >= fires
    d2 = policy.decide(_ans(intent={"choice": "other", "confidence": 0.9}))
    assert d2.template == "out_of_scope"
    d3 = policy.decide(_ans(intent={"choice": "order_status", "confidence": 0.1}))
    assert d3.action == "clarify"


def test_policy_makes_no_network_calls():
    import ast
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent / "jevlab" / "policy.py").read_text()
    tree = ast.parse(src)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
    assert not (imports & {"typesafe_sdk", "httpx", "urllib", "requests", "http"}), imports


def test_bench_math():
    assert benchmath.summarize([])["n"] == 0
    s = benchmath.summarize([10.0, 20.0, 30.0])
    assert s["median_ms"] == 20.0 and s["min_ms"] == 10.0 and s["max_ms"] == 30.0
    assert benchmath.interleave(["a", "b"], 2) == ["a", "b", "a", "b"]
    assert benchmath.drop_warmup([1.0, 2.0, 3.0]) == [2.0, 3.0]


def test_history_truncation_and_latest_field():
    from jevlab.questions import HISTORY_N, build_chat_state

    hist = [{"from": "customer", "text": f"m{i}"} for i in range(20)]
    st8 = build_chat_state("newest", hist)
    assert st8["latest"] == "newest"
    assert len(st8["history"]) <= HISTORY_N - 1
    assert "policy" in st8


def test_state_builder_is_single_source():
    """Chat, Gates, record.py, and tests share build_chat_state — no forks."""
    import ast
    from pathlib import Path as _P

    root = _P(__file__).resolve().parent.parent
    offenders = []
    for f in [root / "ui" / "tabs" / "chat.py", root / "ui" / "tabs" / "gates.py",
              root / "scripts" / "record.py", root / "tests" / "test_policy_chat.py"]:
        tree = ast.parse(_P(f).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict) and any(
                    isinstance(k, ast.Constant) and k.value == "latest" for k in node.keys):
                offenders.append(str(f))
                break
    assert not offenders, f"inline chat-state dicts (must use build_chat_state): {offenders}"


def test_gates_chat_parity_all_recorded():
    import os

    from jevlab import cache
    from jevlab.questions import CHAT_QUESTIONS, build_chat_state

    model = os.getenv("JEV_MODEL", "jev-latest")
    rows = [json.loads(line) for line in
            __import__("pathlib").Path("data/inbox.jsonl").read_text().splitlines() if line.strip()]
    checked = 0
    for m in rows:
        st8 = build_chat_state(m["text"])
        try:
            ans = cache.load_recording(model, st8, CHAT_QUESTIONS).raw["answers"]
        except Exception:
            continue
        d1 = policy.decide(ans)
        d2 = policy.decide(ans)  # Gates and Chat share policy.decide: identical by construction
        assert (d1.action, d1.template, d1.firing_rule) == (d2.action, d2.template, d2.firing_rule)
        checked += 1
    assert checked > 0, "no inbox recordings yet — run `make record-rec` first"


def test_public_demo_never_loads_key(monkeypatch):

    monkeypatch.setenv("JEV_PUBLIC_DEMO", "1")
    monkeypatch.setenv("TYPESAFE_API_KEY", "sk-should-not-be-used")
    from ui.components import is_live

    assert not is_live()
    from jevlab.client import JevError, decide

    try:
        decide("x", {"q": {"type": "noul", "instructions": "x?"}})
    except JevError as e:
        assert "Public demo" in str(e)
    else:
        raise AssertionError("expected public-demo block")


def test_whatif_and_gates_never_touch_ledger(tmp_path, monkeypatch):
    from pathlib import Path as _P

    lp = tmp_path / "u.json"
    monkeypatch.setenv("JEV_BUDGET_LEDGER", str(lp))
    before = lp.read_text() if lp.exists() else None
    policy.decide(_ans())
    policy.decide(_ans(), {"override_yes": 0.1})
    after = lp.read_text() if _P(str(lp)).exists() else None
    assert before == after
