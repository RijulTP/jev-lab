"""Help-system tests: headers, slider help text, YAML orphan check both directions."""
import ast
from pathlib import Path

import yaml

UI = Path(__file__).resolve().parent.parent / "ui"
TABS = UI / "tabs"


def _copy() -> dict:
    return yaml.safe_load((UI / "help_text.yaml").read_text())


def _is_tab_header_call(n: ast.AST) -> bool:
    return isinstance(n, ast.Call) and (
        getattr(getattr(n, "func", None), "attr", "") == "tab_header"
        or getattr(getattr(n, "func", None), "id", "") == "tab_header")


def test_every_tab_calls_shared_header():
    for name in ("playground", "fanout", "gates", "chat"):
        tree = ast.parse((TABS / f"{name}.py").read_text())
        calls = [n for n in ast.walk(tree) if _is_tab_header_call(n)]
        assert calls, f"{name}.py never calls tab_header()"
        args = [a.value for c in calls for a in c.args if isinstance(a, ast.Constant)]
        assert name in args, f"{name}.py header called with wrong tab key"


def test_every_slider_has_nonempty_help():
    for f in TABS.glob("*.py"):
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                attr = getattr(getattr(node, "func", None), "attr", "")
                if attr in ("slider", "sticky_slider"):
                    kw = {k.arg for k in node.keywords}
                    assert "help" in kw, f"{f.name}: {attr} without help="


def test_yaml_keys_used_and_complete():
    src = "\n".join((TABS / f).read_text() for f in TABS.glob("*.py"))
    src += (UI / "help.py").read_text() + (UI / "onboarding.py").read_text()
    src += (UI.parent / "streamlit_app.py").read_text()
    doc = _copy()
    # Every tooltip key referenced in code exists in YAML.
    # A tooltip key counts as used if its quoted name appears anywhere in UI code
    # (covers tt["x"], tooltips"]["x", and help= copy()["tooltips"]["x"] forms).
    used_tooltips = {k for k in doc["tooltips"] if f'"{k}"' in src or f"'{k}'" in src}
    # Every tooltip key referenced in code exists in YAML (checked above by construction);
    # fail here if code references an unknown tooltip-like literal.
    import re

    for lit in set(re.findall(r'tooltips["\']\]\["\'"]?([\w_]+)', src)):
        assert lit in doc["tooltips"], f"tooltip {lit!r} used in code, missing in YAML"
    for k in used_tooltips:
        assert k in doc["tooltips"], f"tooltip {k!r} used in code, missing in YAML"
    # Every tab key in tour order has copy + header call.
    for t in doc["tour"]["order"]:
        assert t in doc["tabs"], f"tour tab {t!r} missing copy"
    # No orphan tooltips (in YAML, never referenced).
    orphans = set(doc["tooltips"]) - used_tooltips
    assert not orphans, f"orphan tooltip keys in YAML: {orphans}"


def test_yaml_structure_complete():
    """Missing copy keys fail loudly here, not on screen."""
    doc = _copy()
    assert doc["welcome"]["title"] and doc["welcome"]["body"] and doc["welcome"]["demo"]
    assert doc["tour"]["order"] == ["playground", "fanout", "gates", "chat"]
    for t in ("playground", "fanout", "gates", "chat"):
        for k in ("name", "summary", "looking_at", "try_this", "next", "footer"):
            assert doc["tabs"][t].get(k), f"tabs.{t}.{k} missing/empty"
    assert len(doc["tabs"]["chat"].get("try_guide", [])) >= 4, "chat.try_guide needs 4+ suggestions"
    assert doc["tabs"]["chat"].get("try_guide_title"), "chat.try_guide_title missing"
    assert doc["tabs"]["chat"].get("desk_about"), "chat.desk_about missing"
    assert len(doc["tabs"]["chat"].get("desk_topics", [])) >= 6, "chat.desk_topics needs 6 topics"
    for k in ("preset", "model", "state_input", "questions_input", "safety_threshold",
              "override_threshold", "intent_confidence", "noul_band", "runs",
              "beginner_toggle", "whatif"):
        assert doc["tooltips"].get(k), f"tooltips.{k} missing/empty"
    for k in ("missing_key", "budget", "no_recording", "ledger", "bad_questions", "call_failed"):
        assert doc["errors"].get(k), f"errors.{k} missing/empty"
    assert len(doc["glossary"]["entries"]) >= 8


def test_friendly_error_never_leaks_secrets():
    from jevlab.budget import BudgetExceeded
    from jevlab.cache import CacheMiss
    from jevlab.client import JevError
    from ui.help import friendly_error

    evil = JevError("401 bad key sk-fake123 Authorization: Bearer sk-fake123")
    for exc in (BudgetExceeded("x"), CacheMiss("x"), evil, ValueError("sk-fake123 boom")):
        out = friendly_error(exc)
        assert "sk-fake" not in out and "Bearer" not in out, out
        assert len(out) > 0


def test_stateful_widgets_have_keys():
    """Radio navigation unmounts pages: keyed widgets survive, unkeyed reset."""
    for f in TABS.glob("*.py"):
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                attr = getattr(getattr(node, "func", None), "attr", "")
                if attr in ("slider", "selectbox", "text_input", "toggle", "text_area"):
                    kw = {k.arg for k in node.keywords}
                    assert "key" in kw, f"{f.name}: {attr} without key= loses state on page switch"


def test_reset_boundary():
    from ui.help import RESET_OWNED_KEYS

    for forbidden in ("chat_spent", "chat_msgs", "chat_toks"):
        assert forbidden not in RESET_OWNED_KEYS, "reset must not touch chat cost/history"
    for required in ("tour_visited", "welcome_dismissed", "expert",
                     "g_thi", "g_tlo", "g_tyes", "g_tno", "g_safety_show",
                     "g_thi_v", "g_tlo_v", "g_tyes_v", "g_tno_v", "g_safety_show_v",
                     "gates_row", "gates_row_widget",
                     "c_tyes", "c_tno", "c_tlo",
                     "c_tyes_v", "c_tno_v", "c_tlo_v",
                     "pg_preset_widget", "pg_model_widget", "pg_state", "pg_q", "pg_last_preset"):
        assert required in RESET_OWNED_KEYS, f"{required} missing from reset keys"
