"""Re-record demo responses from the live API. Requires TYPESAFE_API_KEY."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from jevlab import cache
from jevlab.client import decide


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="Re-record even if a recording exists")
    ap.add_argument("--where", default="", help="Where measured, e.g. home-fiber/eu (stored in meta)")
    ap.add_argument("--dry-run", action="store_true", help="Estimate tokens/cost, record nothing")
    ap.add_argument("--max-presets", type=int, default=0, help="Cap presets per run (0 = all)")
    args = ap.parse_args()

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
