"""Re-record demo responses from the live API. Requires TYPESAFE_API_KEY."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from pathlib import Path

import yaml

from jevlab import cache
from jevlab.client import decide


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="Re-record even if a recording exists")
    ap.add_argument("--where", default="", help="Where measured, e.g. home-fiber/eu (stored in meta)")
    ap.add_argument("--dry-run", action="store_true", help="Estimate tokens/cost, record nothing")
    ap.add_argument("--max-presets", type=int, default=0, help="Cap presets per run (0 = all)")
    ap.add_argument("--inbox", action="store_true", help="Record the 30-message inbox with CHAT_QUESTIONS")
    ap.add_argument("--chat-scripts", action="store_true",
                    help="Record scripted multi-turn states (deterministic templates, exact replay)")
    args = ap.parse_args()

    if os.getenv("JEV_PUBLIC_DEMO", "") == "1":
        print("ERROR: refusing to record with JEV_PUBLIC_DEMO=1 (public demo builds never spend).")
        sys.exit(1)

    from ui.tabs.playground import PRESETS

    model = os.getenv("JEV_MODEL", "jev-latest")
    if not os.getenv("TYPESAFE_API_KEY"):
        print("ERROR: TYPESAFE_API_KEY not set. Copy .env.example to .env first.")
        sys.exit(1)
    from typesafe_sdk import Choice, Noul, Score

    def to_sdk(plain: dict) -> dict:
        out = {}
        for k, q in plain.items():
            t = q.get("type")
            if t == "choice":
                out[k] = Choice(instructions=q["instructions"], criteria=q.get("criteria", {}))
            elif t == "score":
                out[k] = Score(instructions=q["instructions"], criteria=q.get("criteria", []))
            else:
                out[k] = Noul(instructions=q["instructions"])
        return out

    from jevlab.budget import estimate_tokens, status, tokens_to_usd

    if args.inbox:
        import json as _j

        from jevlab.questions import CHAT_QUESTIONS, build_chat_state

        rows = [_j.loads(line) for line in
                Path("data/inbox.jsonl").read_text().splitlines() if line.strip()]
        todo_inbox = []
        for m in rows:
            st8 = build_chat_state(m["text"])
            todo_inbox.append((m["id"], st8))
        if args.dry_run:
            total = sum(estimate_tokens(s, CHAT_QUESTIONS) for _, s in todo_inbox)
            bst = status()
            print(f"DRY RUN inbox: {len(todo_inbox)} msgs, est {total} tok (~${tokens_to_usd(total):.4f}); "
                  f"spent ${bst.get('spent_usd', 0):.4f} / cap ${bst.get('cap_usd', 0):.2f}.")
            return
        for mid, st8 in todo_inbox:
            if not args.force:
                try:
                    cache.load_recording(model, st8, CHAT_QUESTIONS)
                    print(f"Skip (recorded): {mid}")
                    continue
                except Exception:  # noqa: S110 — miss means needs recording
                    pass
            print(f"Recording inbox: {mid} ...")
            result = decide(st8, to_sdk(CHAT_QUESTIONS), model=model, command="record")
            path = cache.save_recording(model, st8, CHAT_QUESTIONS, result,
                                        result.latency_ms, retry_count=0, where=args.where)
            print(f"  -> {path} ({result.latency_ms:.0f}ms, {result.input_tokens} in-tok)")
        return

    if args.chat_scripts:
        import json as _j

        from jevlab import policy as _policy
        from jevlab.questions import CHAT_QUESTIONS, build_chat_state

        scripts = _j.loads(Path("data/chat_scripts.json").read_text())["scripts"]
        templates = yaml.safe_load(Path("data/templates.yaml").read_text())

        if args.dry_run:
            n_turns = sum(len(s["turns"]) for s in scripts)
            print(f"DRY RUN chat-scripts: {n_turns} turns across {len(scripts)} scripts. Recording nothing.")
            return

        def ensure_state(st8: dict, name: str):
            if not args.force:
                try:
                    return cache.load_recording(model, st8, CHAT_QUESTIONS)
                except Exception:  # noqa: S110 — miss means needs recording
                    pass
            print(f"Recording script: {name} ...")
            result = decide(st8, to_sdk(CHAT_QUESTIONS), model=model, command="record")
            path = cache.save_recording(model, st8, CHAT_QUESTIONS, result,
                                        result.latency_ms, retry_count=0, where=args.where)
            print(f"  -> {path} ({result.latency_ms:.0f}ms, {result.input_tokens} in-tok)")
            return result

        for script in scripts:
            hist: list = []
            for i, turn in enumerate(script["turns"]):
                st8 = build_chat_state(turn, hist)
                result = ensure_state(st8, f"{script['name']} t{i + 1}")
                # Deterministic history: policy + canned template, same as the Chat tab.
                dec = _policy.decide(result.raw["answers"])
                hist.append({"from": "customer", "text": turn})
                hist.append({"from": "agent",
                             "text": templates.get(dec.template, {}).get("text", "").format(detail=turn[:60])})
        return

    todo = PRESETS[: args.max_presets] if args.max_presets else PRESETS
    if args.dry_run:
        total = sum(estimate_tokens(p["state"], p["questions"]) for p in todo)
        st = status()
        print(f"DRY RUN: {len(todo)} presets, est {total} tok (~${tokens_to_usd(total):.4f}); "
              f"spent ${st.get('spent_usd', 0):.4f} / cap ${st.get('cap_usd', 0):.2f}. Recording nothing.")
        return
    for p in todo:
        if not args.force:
            try:
                cache.load_recording(model, p["state"], p["questions"])
                print(f"Skip (recorded, use --force): {p['name']}")
                continue
            except Exception:  # noqa: S110 — miss means needs recording
                pass
        print(f"Recording: {p['name']} ...")
        result = decide(p["state"], to_sdk(p["questions"]), model=model, command="record")
        path = cache.save_recording(model, p["state"], p["questions"], result,
                                    result.latency_ms, retry_count=0, where=args.where)
        print(f"  -> {path} ({result.latency_ms:.0f}ms, {result.input_tokens} in-tok, "
              f"resolved={result.model})")


if __name__ == "__main__":
    main()
