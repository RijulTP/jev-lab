"""Support Desk Chat: chat left, decision-first 'What just happened' panel right."""
from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st
import yaml

from jevlab import cache, policy
from jevlab.budget import tokens_to_usd
from jevlab.client import decide
from jevlab.questions import CHAT_QUESTIONS, build_chat_state, build_sdk
from ui import explain
from ui.components import is_live, status_line
from ui.snippets import as_curl, as_python

DATA = Path(__file__).resolve().parent.parent.parent / "data"

# Hero chips: normal, angry, injection. Rest + script live under "More examples".
CHIP_IDS = ("m01", "m07", "m13")

_ACTION_VERB = {
    "refuse": "Refused",
    "urgent_handoff": "Handed to a human (urgent)",
    "handoff": "Handed to a human",
    "clarify": "Asking one clarifying question",
    "reply": "Replying",
}


def _templates() -> dict:
    return yaml.safe_load((DATA / "templates.yaml").read_text())


def _inbox() -> list[dict]:
    return [json.loads(line) for line in (DATA / "inbox.jsonl").read_text().splitlines() if line.strip()]


def _build_state(latest: str, history: list[dict]) -> dict:
    return build_chat_state(latest, history)


def _answer(latest: str, history: list[dict], model: str):
    """Live call or replay. Returns (answers, latency_ms, in_tok, recorded_at, where)."""
    from jevlab.config import validate_questions

    state = _build_state(latest, history)
    if is_live():
        validate_questions(CHAT_QUESTIONS)
        r = decide(state, build_sdk(CHAT_QUESTIONS), model=model, command="chat")
        return r.answers, r.latency_ms, r.input_tokens, None, ""
    r = cache.load_recording(model, state, CHAT_QUESTIONS)
    return r.answers, r.latency_ms, r.input_tokens, r.recorded_at, ""


def _reply_text(template: str, latest: str) -> str:
    return _templates().get(template, {}).get("text", "").format(detail=latest[:60])


def _decision_card(dec, thresholds: dict):
    verb = _ACTION_VERB.get(dec.action, dec.action)
    reason = next((t.reason for t in dec.trace if t.fired), dec.note)
    extra = f" Template: `{dec.template}`." if dec.action == "reply" else ""
    st.info(f"**{verb}**, because {reason}.{extra}")


def render():
    st.header("Support Desk Chat")
    from ui.help import copy as help_copy
    from ui.help import friendly_error, is_expert, tab_header

    tab_header("chat")
    live = is_live()
    model = os.getenv("JEV_MODEL", "jev-latest")
    beginner = not is_expert()
    tt = help_copy()["tooltips"]

    if "chat_msgs" not in st.session_state:
        st.session_state.chat_msgs = []
        st.session_state.chat_spent = 0.0
        st.session_state.chat_toks = []

    t_yes = float(st.session_state.get("c_tyes_v", 0.75))
    t_no = float(st.session_state.get("c_tno_v", 0.25))
    t_lo = float(st.session_state.get("c_tlo_v", 0.50))
    thresholds = {"override_yes": t_yes, "safety_yes": round((t_yes + t_no) / 2, 2),
                  "human_yes": t_yes, "intent_conf_lo": t_lo}

    left, right = st.columns([1, 1.2])

    def handle_user(text: str):
        hist = [{"from": m["role"], "text": m["text"]} for m in st.session_state.chat_msgs]
        try:
            with st.spinner("Asking Jev…"):
                answers, ms, toks, rec_at, where = _answer(text, hist, model)
        except Exception as e:
            st.error(friendly_error(e))
            return
        dec = policy.decide(answers, thresholds)
        cost = tokens_to_usd(toks)
        st.session_state.chat_spent += cost
        st.session_state.chat_toks.append(toks)
        st.session_state.chat_msgs.append(
            {"role": "customer", "text": text, "answers": answers, "latency_ms": ms,
             "tokens": toks, "cost": cost, "recorded_at": rec_at, "where": where,
             "decision": {"action": dec.action, "template": dec.template,
                          "firing_rule": dec.firing_rule, "note": dec.note,
                          "trace": [{"rule": t.rule, "fired": t.fired, "reason": t.reason} for t in dec.trace]},
             "thresholds": dict(thresholds)})
        st.session_state.chat_msgs.append(
            {"role": "agent", "text": _reply_text(dec.template, text), "template": dec.template})

    def fresh_handle(text: str):
        st.session_state.chat_msgs = []
        st.session_state.chat_spent = 0.0
        st.session_state.chat_toks = []
        handle_user(text)

    with left:
        for m in st.session_state.chat_msgs:
            with st.chat_message("user" if m["role"] == "customer" else "assistant"):
                st.write(m["text"])
        ct = help_copy()["tabs"]["chat"]
        st.caption(ct["desk_about"])
        with st.expander(ct["try_guide_title"], expanded=beginner):
            for topic in ct["desk_topics"]:
                st.markdown(f"- {topic}")
            st.markdown("---")
            for line in ct["try_guide"]:
                st.markdown(f"- {line}")
            if live:
                st.markdown(f"- {ct['try_guide_live']}")
        if not live:
            st.caption("Demo examples — each starts fresh. " + help_copy()["disabled_reasons"]["typing"])
            rows = {m["id"]: m for m in _inbox()}
            cols = st.columns(3)
            for col, mid, chip in zip(cols, CHIP_IDS, ("Normal", "Angry", "Injection")):
                with col:
                    if st.button(chip, key=f"demo_{mid}"):
                        fresh_handle(rows[mid]["text"])
            with st.expander("More examples"):
                for m in _inbox()[:8]:
                    if m["id"] in CHIP_IDS:
                        continue
                    if st.button(f"{m['id']}: {m['text'][:50]}…", key=f"demo_{m['id']}"):
                        fresh_handle(m["text"])
                if st.button("▶ Scripted 3-turn conversation", key="chat_script"):
                    import json as _j

                    script = _j.loads((DATA / "chat_scripts.json").read_text())["scripts"][0]
                    st.session_state.chat_msgs = []
                    st.session_state.chat_spent = 0.0
                    st.session_state.chat_toks = []
                    for turn in script["turns"]:
                        handle_user(turn)
        else:
            text = st.chat_input("Type a customer message…")
            if text:
                handle_user(text)
        if st.button("Reset conversation", key="chat_reset"):
            st.session_state.chat_msgs = []
            st.session_state.chat_spent = 0.0
            st.session_state.chat_toks = []

    with right:
        st.subheader("What just happened")
        cust = [m for m in st.session_state.chat_msgs if m["role"] == "customer"]
        if not cust:
            st.caption(help_copy()["empty"]["chat"])
            st.caption(help_copy()["tabs"]["chat"]["next"])
            return
        last = cust[-1]
        re = policy.decide(last["answers"], thresholds)
        flipped = re.firing_rule != last["decision"]["firing_rule"]
        status_line(live, last.get("recorded_at"), model, last["latency_ms"], last["tokens"])
        _decision_card(re, thresholds)
        if flipped:
            st.warning(f"What-if: same answers now decide `{re.firing_rule}` instead of "
                       f"`{last['decision']['firing_rule']}` — no new API call.")
        with st.expander("1 · State", expanded=False):
            explain.step_build_state(_build_state(last["text"], []), last["tokens"], beginner)
        with st.expander("2 · One Jev call", expanded=False):
            explain.step_ask(last["latency_ms"], last["tokens"], last["cost"],
                             st.session_state.chat_spent, beginner)
        with st.expander("3 · Answers", expanded=False):
            explain.step_answers(last["answers"], beginner)
        with st.expander("4 · Rules", expanded=True):
            explain.step_rules(type("D", (), {"trace": re.trace, "firing_rule": re.firing_rule,
                                              "note": re.note})(), beginner)
        with st.expander("5 · Reply", expanded=False):
            explain.step_reply(re.template, _reply_text(re.template, last["text"]))
        with st.expander("What if I change a threshold?", expanded=False):
            st.caption(tt["whatif"])
            from ui.help import sticky_slider

            t_yes = sticky_slider("Noul act-yes above", "c_tyes", 0.75, help=tt["override_threshold"])
            t_no = sticky_slider("Noul act-no below", "c_tno", 0.25, help=tt["noul_band"])
            t_lo = sticky_slider("Intent review below", "c_tlo", 0.50, help=tt["intent_confidence"])
            st.caption(f"Safety bar sits at {(t_yes + t_no) / 2:.2f}. Re-decides instantly, no new call.")
        if is_expert():
            with st.expander("State growth"):
                st.bar_chart(st.session_state.chat_toks)
            with st.expander("Copy this request as cURL / Python"):
                st.code(as_curl(model, _build_state(last["text"], []), CHAT_QUESTIONS), language="bash")
                st.code(as_python(model, _build_state(last["text"], []), CHAT_QUESTIONS), language="python")
            with st.expander("Raw JSON"):
                st.code(json.dumps({"answers": last["answers"]}, indent=2)[:3000], language="json")
    from ui.help import copy as _hc

    st.caption(_hc()["tabs"]["chat"]["next"])
