"""Shared Streamlit widgets: status line, probability bars, raw JSON panel."""
from __future__ import annotations

import json
import os

import streamlit as st


def public_demo() -> bool:
    return os.getenv("JEV_PUBLIC_DEMO", "") == "1"


def is_live() -> bool:
    if public_demo():
        return False
    return bool(os.getenv("TYPESAFE_API_KEY", ""))


def status_line(live: bool, recorded_at: str | None = None, model: str = "",
                ms: float | None = None, toks: int | None = None):
    """One status line replacing badge + stamp + stats."""
    bits = ["Live" if live else "Demo"]
    if recorded_at:
        bits.append(f"recorded {recorded_at[:10]}")
    if model:
        bits.append(model)
    if ms is not None:
        bits.append(f"{ms:.0f} ms")
    if toks is not None:
        bits.append(f"{toks} tokens")
    st.caption(" · ".join(bits))


def prob_bars(answer: dict):
    probs = answer.get("probabilities") or {}
    if not probs:
        if answer.get("type") == "noul":
            st.progress(float(answer.get("noul", 0.0)), text=f"P(yes) = {answer.get('noul')}")
        return
    for k, v in sorted(probs.items(), key=lambda kv: -kv[1]):
        st.progress(float(v), text=f"{k}: {float(v):.2f}")
    if "confidence" in answer:
        st.caption(f"confidence (separate from probability): {answer['confidence']:.2f}")


def raw_json_panel(request: dict, response: dict):
    with st.expander("Raw request/response JSON", expanded=False):
        st.code(json.dumps(request, indent=2), language="json")
        st.code(json.dumps(response, indent=2), language="json")
