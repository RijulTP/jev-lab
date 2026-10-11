import streamlit as st


def render():
    st.header("Parallel fan-out")
    st.caption("v2: 1 batched call vs 8 sequential vs 8 parallel-client; median of N runs.")
    st.info("Not yet implemented in this Phase-1 slice. Ships after Playground + `make record`.")
