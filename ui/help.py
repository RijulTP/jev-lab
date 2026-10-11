"""Helpers over ui/help_text.yaml. Single source for copy, headers, friendly errors."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import streamlit as st
import yaml

_YAML = Path(__file__).with_name("help_text.yaml")

# Widget-state keys Reset-view owns. Ledger, recordings, and chat cost excluded on purpose.
RESET_OWNED_KEYS = [
    "tour_visited", "tour_nav", "welcome_dismissed", "expert", "expert_toggle",
    "g_thi", "g_tlo", "g_tyes", "g_tno", "g_safety_show",
    "g_thi_v", "g_tlo_v", "g_tyes_v", "g_tno_v", "g_safety_show_v",
    "gates_row", "gates_row_widget",
    "c_tyes", "c_tno", "c_tlo",
    "c_tyes_v", "c_tno_v", "c_tlo_v",
    "pg_preset_widget", "pg_model_widget", "pg_state", "pg_q", "pg_last_preset",
]


@lru_cache(maxsize=1)
def copy() -> dict:
    return yaml.safe_load(_YAML.read_text())


def tab_header(tab: str):
    """Slim header: one-line summary + single Try-this line + About expander (with footer)."""
    t = copy()["tabs"][tab]
    st.caption(t["summary"])
    st.markdown(f"**Try this:** {t['try_this']}")
    with st.expander("About this page"):
        st.write(t["looking_at"])
        st.caption(t["footer"])
    st.session_state.setdefault("tour_visited", [])
    if tab not in st.session_state.tour_visited:
        st.session_state.tour_visited = [*st.session_state.tour_visited, tab]


def _goto_tab(tab: str):
    st.session_state.tour_nav = tab


def next_button(tab: str):
    """Bottom-of-tab Next button. on_click runs before widgets instantiate,
    so assigning the radio's key is legal here (plain assignment would raise)."""
    label = f"Next: {copy()['tabs'][tab]['name']} →"
    st.button(label, key=f"next_{tab}", type="primary", on_click=_goto_tab, args=(tab,))


def is_expert() -> bool:
    return bool(st.session_state.get("expert", False))


def friendly_error(exc: Exception) -> str:
    """Fixed one-liners. Raw exception text, headers, and keys never reach the screen."""
    from jevlab.budget import BudgetExceeded, LedgerError
    from jevlab.cache import CacheMiss
    from jevlab.client import JevError

    e = copy()["errors"]
    if isinstance(exc, BudgetExceeded):
        return e["budget"]
    if isinstance(exc, LedgerError):
        return e["ledger"]
    if isinstance(exc, CacheMiss):
        return e["no_recording"]
    if isinstance(exc, JevError):
        msg = str(exc)
        if "TYPESAFE_API_KEY" in msg or "Missing" in msg:
            return e["missing_key"]
        return e["call_failed"]
    return e["call_failed"]


def reset_view():
    for k in RESET_OWNED_KEYS:
        st.session_state.pop(k, None)
    st.session_state["welcome_dismissed"] = False
    st.session_state["tour_visited"] = []


def sticky_slider(label: str, key: str, default: float, help: str = "") -> float:
    """Slider whose value survives page switches: canonical value lives in `<key>_v`.

    Widget remounts (radio navigation, AppTest) reapply their default; the mirror
    re-seeds the widget on mount and is written back on every render.
    """
    mirror = f"{key}_v"
    st.session_state.setdefault(mirror, default)
    val = st.slider(label, 0.0, 1.0, float(st.session_state[mirror]), 0.05,
                    key=key, help=help)
    st.session_state[mirror] = float(val)
    return float(val)
