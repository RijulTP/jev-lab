"""Welcome card, tour checklist + closing card, glossary."""
from __future__ import annotations

import streamlit as st

from ui.help import copy


def welcome_card():
    if st.session_state.get("welcome_dismissed", False):
        return
    w = copy()["welcome"]
    st.success(f"**{w['title']}.** {w['body']}")
    st.caption(f"{w['demo']} {w['cta']}")
    if st.button("Dismiss", key="welcome_dismiss"):
        st.session_state.welcome_dismissed = True


def tour_sidebar(order: list[str], current: str) -> str:
    """Free navigation radio with ✓ marks. Returns the selected page."""
    visited = st.session_state.get("tour_visited", [])
    names = {p: copy()["tabs"][p]["name"] for p in order}
    labels = {p: f"{'✓ ' if p in visited else ''}{names[p]}" for p in order}
    sel = st.sidebar.radio("Pages", order, index=order.index(current),
                           format_func=lambda p: labels[p], key="tour_nav",
                           help=copy()["tour"]["subtitle"])
    if len([p for p in order if p in visited]) == len(order):
        d = copy()["tour"]
        st.sidebar.success(f"**{d['done_title']}.** {d['done_body']}")
    return sel


def glossary_body():
    g = copy()["glossary"]
    for term, desc in g["entries"].items():
        st.markdown(f"**{term}.** {desc}")


def glossary():
    with st.sidebar.expander(copy()["glossary"]["title"]):
        glossary_body()


def help_button():
    if st.sidebar.button("Help", key="help_reopen"):
        st.session_state.welcome_dismissed = False
