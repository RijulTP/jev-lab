"""jev-lab entrypoint: `streamlit run streamlit_app.py` or `make run`."""
from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from ui import onboarding
from ui.components import is_live, public_demo
from ui.help import copy, reset_view
from ui.tabs import chat, fanout, gates, playground

st.set_page_config(page_title="jev-lab", layout="wide")
st.title("jev-lab — Jev demo companion")

ORDER = copy()["tour"]["order"]
PAGES = {"playground": playground, "fanout": fanout, "gates": gates, "chat": chat}

# Sidebar: navigator, Expert toggle, mode + Why?, Help expander. Identical on every page.
st.session_state.setdefault("expert", False)
expert = st.sidebar.toggle("Expert view", value=st.session_state.expert,
                           help=copy()["tooltips"]["beginner_toggle"], key="expert_toggle")
st.session_state.expert = expert
st.sidebar.caption("Expert view shows raw JSON and field names.")

live = is_live()
st.sidebar.markdown("● Live" if live else "● Demo")
with st.sidebar.popover("Why?"):
    st.write(copy()["mode_popover"])

if live and not public_demo():
    try:
        from jevlab.budget import status as _budget_status

        _bst = _budget_status()
        if "error" in _bst:
            st.sidebar.error(f"Budget ledger error — live calls blocked. {_bst['error']}")
        else:
            color = "green" if not _bst.get("warn_at_80") else "orange"
            st.sidebar.markdown(
                f":{color}[Budget: ${_bst['spent_usd']:.4f} / ${_bst['cap_usd']:.2f}]"
            )
    except Exception:  # noqa: S110 — budget pill is best-effort; ledger errors show in doctor
        pass

with st.sidebar.expander("Help"):
    onboarding.glossary_body()
    if st.button("Show welcome", key="help_reopen"):
        st.session_state.welcome_dismissed = False
    if st.button("Reset view", key="reset_view"):
        reset_view()

current = st.session_state.get("tour_nav", ORDER[0])
if current not in ORDER:
    current = ORDER[0]
onboarding.welcome_card()
page = onboarding.tour_sidebar(ORDER, current)
PAGES[page].render()
