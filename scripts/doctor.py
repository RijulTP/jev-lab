"""Check Python version, key, connectivity, model list. Friendly fixes."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from jevlab.config import is_stale, load_limits, staleness_days


def main() -> None:
    ok = True
    print(f"Python: {sys.version.split()[0]} (need >=3.11)")
    if sys.version_info < (3, 11):
        print("  FIX: install Python 3.11+ (https://www.python.org/downloads/)")
        ok = False
    try:
        import streamlit  # noqa: F401
        import typesafe_sdk  # noqa: F401

        print("Deps: streamlit + typesafe-sdk installed")
    except ImportError as e:
        print(f"Deps MISSING: {e}\n  FIX: run `make setup` (or `uv sync`)")
        ok = False
    key = os.getenv("TYPESAFE_API_KEY", "")
    print(f"Key: {'set' if key else 'NOT set (demo mode only)'}")
    if not key:
        print("  FIX: copy .env.example to .env and add TYPESAFE_API_KEY for live mode + `make record`.")
    lim = load_limits()
    print(f"Limits (as of {lim.get('as_of')}): {lim.get('context_total_tokens')} total / "
          f"{lim.get('context_state_plus_longest_question_tokens')} state+longest-Q, "
          f"${lim.get('price_input_per_mtok_usd')}/M in-tok, output free")
    print(f"Choice<= {lim.get('choice_max_options')} options; Score {lim.get('score_min_levels')}-"
          f"{lim.get('score_max_levels')} levels; text-only={lim.get('input_text_only')}")
    if is_stale(lim):
        print(f"STALE: limits as_of {lim.get('as_of')} is {staleness_days(lim)} days old "
              f"(>{lim.get('staleness_warn_days')}d). Recheck {lim.get('sources', {}).get('models')}.")
        ok = False
    from jevlab.budget import status as budget_status

    bst = budget_status()
    if "error" in bst:
        print(f"Budget ledger: ERROR — {bst['error']}")
        ok = False
    else:
        print(f"Budget: spent ${bst['spent_usd']:.4f} / cap ${bst['cap_usd']:.2f} "
              f"(remaining ${bst['remaining_usd']:.4f}, {bst['calls']} calls)")
        if bst.get("warn_at_80"):
            print("  WARN: over 80% of budget cap.")
    print("Note: client ledger is project-local only — check console.typesafe.ai for "
          "server-side spend limits/alerts and reconcile after first record.")
    if key:
        try:
            from typesafe_sdk import TypeSafeClient

            with TypeSafeClient() as client:
                models = client.models.list().models
            print(f"Connectivity: OK ({len(models)} models: {', '.join(m.name for m in models[:5])})")
        except Exception as e:
            print(f"Connectivity FAILED: {e}\n  FIX: check key, network, retry-after on 429.")
            ok = False
    else:
        print("Connectivity: skipped (no key)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
