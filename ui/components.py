"""Shared Streamlit widgets: mode badge, probability bars, raw JSON panel."""
from __future__ import annotations

import json
import os

import streamlit as st


def is_live() -> bool:
    return bool(os.getenv("TYPESAFE_API_KEY", ""))


def mode_badge(latency_ms: float | None = None, input_tokens: int | None = None,
               recorded_at: str | None = None):
    mode = "LIVE" if is_live() else "DEMO"
    color = "green" if is_live() else "orange"
    extra = ""
    if latency_ms is not None:
        extra += f" · {latency_ms:.0f} ms"
    if input_tokens is not None:
        extra += f" · {input_tokens} in-tok"
    if recorded_at:
        extra += f" · recorded {recorded_at[:10]}"
    st.markdown(f":{color}[● {mode}{extra}]")


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
