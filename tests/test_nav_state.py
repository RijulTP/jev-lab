"""Navigation survival: chat history + slider values persist across radio page switches."""
import os

os.environ.pop("TYPESAFE_API_KEY", None)  # demo mode: replay only, no spend
os.environ["JEV_PUBLIC_DEMO"] = "1"  # ignore repo .env key: deterministic demo, never live

from streamlit.testing.v1 import AppTest

APP = str(__import__("pathlib").Path(__file__).resolve().parent.parent / "streamlit_app.py")

PAGES = {"playground": "Playground", "fanout": "Parallel fan-out",
         "gates": "Confidence gates", "chat": "Support Desk Chat"}


def _goto(at: AppTest, page: str) -> AppTest:
    # Labels gain ✓ prefixes as pages are visited; match by substring.
    options = list(at.sidebar.radio[0].options)
    label = next(o for o in options if PAGES[page] in o)
    at.sidebar.radio[0].set_value(label).run()
    assert not at.exception, f"{page} failed: {at.exception}"
    return at


def test_chat_and_sliders_survive_navigation():
    at = AppTest.from_file(APP).run()
    assert not at.exception, f"boot failed: {at.exception}"

    # Page 1: Chat — demo buttons each start a fresh single-turn conversation.
    at = _goto(at, "chat")
    at.button(key="demo_m01").click().run()
    assert len(at.session_state.get("chat_msgs", [])) == 2, "single-turn demo should give 2 msgs"

    # Scripted 3-turn conversation replays exactly (deterministic templates).
    at.button(key="chat_script").click().run()
    assert len(at.session_state.get("chat_msgs", [])) == 6, "scripted 3-turn should give 6 msgs"

    # Page 2: Gates — move a slider (mirrored value survives remounts).
    at = _goto(at, "gates")
    at.slider(key="g_thi").set_value(0.9).run()
    assert at.session_state.get("g_thi_v") == 0.9

    # Back to Chat: conversation intact.
    at = _goto(at, "chat")
    assert len(at.session_state.get("chat_msgs", [])) == 6, "chat history wiped by navigation"

    # Back to Gates: slider intact via mirror.
    at = _goto(at, "gates")
    assert at.session_state.get("g_thi_v") == 0.9, "slider value wiped by navigation"
    assert at.slider(key="g_thi").value == 0.9, "slider widget not re-seeded from mirror"

    # Next button navigates forward in the tour.
    at.button(key="next_chat").click().run()
    assert at.session_state.get("tour_nav") == "chat", "Next button did not navigate"


def test_reset_restores_defaults_keeps_cost():
    at = AppTest.from_file(APP).run()
    at = _goto(at, "chat")
    at.button(key="demo_m01").click().run()
    spent = at.session_state.get("chat_spent", 0.0)
    at = _goto(at, "gates")
    at.slider(key="g_thi").set_value(0.9).run()
    at.button(key="reset_view").click().run()
    assert at.session_state.get("g_thi", 0.8) != 0.9 or "g_thi" not in at.session_state
    assert at.session_state.get("chat_spent", None) == spent, "reset touched chat cost"
    assert at.session_state.get("expert", False) is False, "reset must restore Beginner ON"
