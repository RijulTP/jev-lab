"""jev-lab entrypoint: `streamlit run streamlit_app.py` or `make run`."""
from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from ui.tabs import calibration, fanout, gates, playground

st.set_page_config(page_title="jev-lab", layout="wide")
st.title("jev-lab — Jev demo companion")

try:
    from jevlab.budget import status as _budget_status

    _bst = _budget_status()
    if "error" in _bst:
        st.sidebar.error(f"Budget ledger error — live calls blocked. {_bst['error']}")
    else:
        color = "green" if not _bst.get("warn_at_80") else "orange"
        st.sidebar.markdown(
            f":{color}[Budget: ${ _bst['spent_usd']:.4f} / ${ _bst['cap_usd']:.2f}]"
        )
except Exception:  # noqa: S110 — budget pill is best-effort; ledger errors show in doctor
    pass

tab1, tab2, tab3, tab4 = st.tabs(["Playground", "Parallel fan-out", "Confidence gates", "Calibration lab"])
with tab1:
    playground.render()
with tab2:
    fanout.render()
with tab3:
    gates.render()
with tab4:
    calibration.render()
