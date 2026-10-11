"""Gates: big counts, safety-first slider, compact table + one detail panel. Replay only."""
from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st

from jevlab import cache, policy
from jevlab.cache import CacheMiss
from jevlab.client import JevError
from jevlab.policy import DEFAULTS
from ui.components import is_live, status_line

DATA = Path(__file__).resolve().parent.parent.parent / "data"


def _inbox() -> list[dict]:
    return [json.loads(line) for line in (DATA / "inbox.jsonl").read_text().splitlines() if line.strip()]


def _build_state(text: str) -> dict:
    from jevlab.questions import build_chat_state

    return build_chat_state(text)


def _answers_for(text: str, model: str) -> dict | None:
    from jevlab.questions import CHAT_QUESTIONS

    try:
        return cache.load_recording(model, _build_state(text), CHAT_QUESTIONS).raw.get("answers", {})
    except (CacheMiss, JevError):
        return None


_ACTION_COLOR = {"auto-handled": "green", "review": "orange", "escalate": "red"}


def render():
    st.header("Confidence gates")
    from ui.help import copy as help_copy
    from ui.help import is_expert, next_button, sticky_slider, tab_header

    tab_header("gates")
    live = is_live()
    model = os.getenv("JEV_MODEL", "jev-latest")
    tt = help_copy()["tooltips"]

    t_yes = float(st.session_state.get("g_tyes_v", DEFAULTS["override_yes"]))
    t_no = float(st.session_state.get("g_tno_v", 0.25))
    t_lo = float(st.session_state.get("g_tlo_v", DEFAULTS["intent_conf_lo"]))
    t_hi = float(st.session_state.get("g_thi_v", DEFAULTS["intent_conf_lo"] + 0.30))
    safety_yes = round((t_yes + t_no) / 2, 2)

    # Safety slider drives the safety bar directly (best demo); override/human stay
    # on the act-yes slider inside "More thresholds". Defaults reproduce frozen policy.
    safety_yes = sticky_slider("Safety handoff at/above", "g_safety_show", safety_yes,
                               help=tt["safety_threshold"])
    # Safety slider drives the safety bar directly (best demo); override/human stay
    # on the act-yes slider inside "More thresholds". Defaults reproduce frozen policy.
    with st.expander("More thresholds"):
        t_hi = sticky_slider("Auto-act at/above", "g_thi", DEFAULTS["intent_conf_lo"] + 0.30,
                             help=tt["intent_confidence"])
        t_lo = sticky_slider("Review at/above", "g_tlo", DEFAULTS["intent_conf_lo"],
                             help=tt["intent_confidence"])
        t_yes = sticky_slider("Act-yes above", "g_tyes", DEFAULTS["override_yes"],
                              help=tt["override_threshold"])
        t_no = sticky_slider("Act-no below", "g_tno", 0.25, help=tt["noul_band"])
    st.caption(f"Safety ≥ {safety_yes:.2f} · override/human ≥ {t_yes:.2f}. "
               f"{help_copy()['tooltips']['safety_threshold']}")

    inbox = _inbox()
    rows: list[dict] = []
    recorded, agree = 0, 0
    for m in inbox:
        ans = _answers_for(m["text"], model)
        if ans is None:
            continue
        recorded += 1
        dec = policy.decide(ans, {"intent_conf_lo": t_lo, "override_yes": t_yes,
                                  "safety_yes": safety_yes, "human_yes": t_yes})
        intent_conf = float((ans.get("intent") or {}).get("confidence", 0.0))
        if dec.action in ("refuse", "urgent_handoff"):
            bucket = "escalate"
        elif intent_conf >= t_hi and dec.action == "reply":
            bucket = "auto-handled"
        else:
            bucket = "review"
        rows.append({"id": m["id"], "message": m["text"][:60], "bucket": bucket,
                     "action": dec.action, "template": dec.template,
                     "rule": dec.firing_rule, "note": dec.note,
                     "expected": f"{m['expected_action']}/{m['expected_template']}",
                     "match": dec.action == m["expected_action"] and dec.template == m["expected_template"],
                     "trace": [{"rule": t.rule, "fired": t.fired, "reason": t.reason} for t in dec.trace]})
        if rows[-1]["match"]:
            agree += 1

    status_line(live, None, model, None, None)
    c1, c2, c3 = st.columns(3)
    counts = {b: sum(1 for r in rows if r["bucket"] == b)
              for b in ("auto-handled", "review", "escalate")}
    c1.metric("Automatic", counts["auto-handled"])
    c2.metric("Review", counts["review"])
    c3.metric("Human", counts["escalate"])
    st.write(f"{agree}/{recorded} agree with my labels (mechanics at defaults, not accuracy).")

    ids = [r["id"] for r in rows]
    st.session_state.setdefault("gates_row", ids[0] if ids else "")
    sel = st.selectbox("Inspect ticket", ids, index=ids.index(st.session_state.gates_row)
                       if st.session_state.gates_row in ids else 0, key="gates_row_widget")
    st.session_state.gates_row = sel
    row = next(r for r in rows if r["id"] == sel)
    dot_color = _ACTION_COLOR[row["bucket"]]
    st.markdown(f"**:{dot_color}[●] {row['id']}** — {row['message']}…")
    st.write(f"Decisive rule: `{row['rule']}` → {row['action']} / {row['template']}"
             + ("" if row["match"] else " ⚠️ differs from hand label"))
    st.caption(row["note"])
    if is_expert():
        with st.expander("Rule trace"):
            for t in row["trace"]:
                st.caption(f"{'✓' if t['fired'] else '✗'} {t['rule']}: {t['reason']}")

    with st.expander("All tickets"):
        st.dataframe([{"id": r["id"], "message": r["message"], "action": r["action"],
                       "rule": r["rule"]} for r in rows], use_container_width=True)
    next_button("chat")
