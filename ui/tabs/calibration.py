import streamlit as st


def render():
    st.header("Calibration lab")
    st.caption("Requires real recordings (`make record`). 5 bins, Wilson CIs, Choice/Score/Noul plotted separately.")
    st.warning("No real recordings yet — this tab activates after a keyed `make record` run. See README caveats.")
