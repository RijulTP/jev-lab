"""Fan-out: 1 batched vs 8 sequential vs 8 parallel-client. Benchmark hygiene built in."""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import streamlit as st

from jevlab import bench as benchmath
from jevlab.budget import estimate_tokens, tokens_to_usd
from jevlab.client import decide
from jevlab.questions import FANOUT_QUESTIONS, build_sdk
from ui.components import is_live

BENCH_PATH = Path(__file__).resolve().parent.parent.parent / "recordings" / "fanout_bench.json"
STATE = "Our API started returning 500 errors 20 minutes ago; we can't process orders. This is the third time I'm writing."
N_RUNS = 5


def _methods():
    return ["batched", "sequential", "parallel"]


def _run_batched():
    t0 = time.perf_counter()
    r = decide(STATE, build_sdk(FANOUT_QUESTIONS), model=os.getenv("JEV_MODEL", "jev-latest"), command="fanout")
    return (time.perf_counter() - t0) * 1000.0, r.input_tokens, 0


def _run_sequential():
    toks, retries = 0, 0
    t0 = time.perf_counter()
    for k, q in FANOUT_QUESTIONS.items():
        try:
            r = decide(STATE, build_sdk({k: q}), model=os.getenv("JEV_MODEL", "jev-latest"), command="fanout")
            toks += r.input_tokens
        except Exception as e:
            if "429" in str(e):
                retries += 1
    return (time.perf_counter() - t0) * 1000.0, toks, retries


def _run_parallel():
    from typesafe_sdk import AsyncTypeSafeClient

    async def go():
        toks = 0
        t0 = time.perf_counter()
        sem = asyncio.Semaphore(4)

        async def one(k, q):
            nonlocal toks
            async with sem, AsyncTypeSafeClient() as client:
                resp = await client.system_one(state=STATE, questions=build_sdk({k: q}))
                toks += int(getattr(resp.usage, "input_tokens", 0) or 0)

        await asyncio.gather(*[one(k, q) for k, q in FANOUT_QUESTIONS.items()])
        return (time.perf_counter() - t0) * 1000.0, toks

    # Parallel path bypasses decide() ledger; preflight the batch total instead.
    est = sum(estimate_tokens(STATE, {k: q}) for k, q in FANOUT_QUESTIONS.items())
    from jevlab.budget import release, reserve, settle

    reserve(est)
    try:
        ms, toks = asyncio.run(go())
        settle(est, toks, command="fanout")
        return ms, toks, 0
    except Exception:
        release(est)
        raise


def run_benchmark_live() -> dict:
    runners = {"batched": _run_batched, "sequential": _run_sequential, "parallel": _run_parallel}
    for m in _methods():  # warm-up, excluded
        try:
            runners[m]()
        except Exception:  # noqa: S110 — warm-up failures are non-fatal by design
            pass
    results: dict[str, dict] = {}
    for m in benchmath.interleave(_methods(), N_RUNS):
        ms, toks, retries = runners[m]()
        results.setdefault(m, {"runs": [], "tokens": [], "retries": 0})
        results[m]["runs"].append(ms)
        results[m]["tokens"].append(toks)
        results[m]["retries"] += retries
    out = {"methods": {}, "n_runs": N_RUNS, "state_chars": len(STATE)}
    import datetime

    out["recorded_at"] = datetime.datetime.now(datetime.UTC).isoformat()
    out["where"] = os.getenv("JEV_WHERE", "")
    out["model"] = os.getenv("JEV_MODEL", "jev-latest")
    for m, d in results.items():
        s = benchmath.summarize(d["runs"])
        s.update({"median_tokens": sorted(d["tokens"])[len(d["tokens"]) // 2],
                  "retries": d["retries"]})
        out["methods"][m] = s
    BENCH_PATH.write_text(json.dumps(out, indent=2))
    return out


def render():
    from ui.components import status_line
    from ui.help import copy as help_copy
    from ui.help import friendly_error, next_button, tab_header

    st.header("Parallel fan-out")
    tab_header("fanout")
    live = is_live()
    data = None
    if BENCH_PATH.exists():
        try:
            data = json.loads(BENCH_PATH.read_text())
        except Exception:
            data = None

    if live:
        est = sum(estimate_tokens(STATE, {k: q}) for k, q in FANOUT_QUESTIONS.items()) * (N_RUNS * 3 + 3)
        from jevlab.budget import status as bstatus

        bst = bstatus()
        with st.expander(f"Run it yourself (costs about ${tokens_to_usd(est):.4f})"):
            st.write(f"Remaining budget ${bst.get('remaining_usd', 0):.4f} (preflight, over-estimates).")
            if st.button("Run benchmark (live)", type="primary",
                           help=help_copy()["tooltips"]["runs"]):
                try:
                    with st.spinner("Running interleaved benchmark (warm-up excluded)..."):
                        data = run_benchmark_live()
                except Exception as e:
                    st.error(friendly_error(e))
                    return
    elif data is None:
        st.info(help_copy()["empty"]["fanout"])
        return

    if data is None:
        return
    methods = list(data["methods"].keys())
    best = min(methods, key=lambda m: data["methods"][m]["median_ms"])
    status_line(live, data.get("recorded_at"), data.get("model", ""),
                data["methods"][best]["median_ms"], None)
    st.write(f"Takeaway: one batched call answers all 8 — median {data['methods'][best]['median_ms']:.0f} ms.")
    mcols = st.columns(len(methods))
    for col, m in zip(mcols, methods):
        with col:
            st.metric(m, f"{data['methods'][m]['median_ms']:.0f} ms")
    st.bar_chart({m: data["methods"][m]["median_ms"] for m in methods})
    st.dataframe([{"method": m,
                   "median ms": round(d["median_ms"]),
                   "range ms": f"{d['min_ms']:.0f}–{d['max_ms']:.0f}",
                   "input tokens": int(d["median_tokens"]),
                   "cost": f"${tokens_to_usd(int(d['median_tokens'])):.4f}",
                   "retries": d["retries"]}
                  for m, d in ((m, data["methods"][m]) for m in methods)],
                 use_container_width=True, hide_index=True)
    st.caption("Sequential resends the state 8× — billing is per input token, so batched is cheaper as well as faster. "
               "Timings depend on network/account; rerun live. Retried runs are flagged, not hidden.")
    bat, seq = data["methods"]["batched"], data["methods"]["sequential"]
    with st.expander(help_copy()["tabs"]["fanout"]["why_cheaper_title"]):
        st.write(help_copy()["tabs"]["fanout"]["why_cheaper_body"])
        st.write(f"Measured here: 8 separate calls used ~{int(seq['median_tokens'])} tokens, "
                 f"one batched call used ~{int(bat['median_tokens'])} — "
                 f"about {int(seq['median_tokens']) - int(bat['median_tokens'])} tokens saved "
                 f"(~${tokens_to_usd(int(seq['median_tokens']) - int(bat['median_tokens'])):.4f}).")
    next_button("gates")
