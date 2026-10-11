"""Budget ledger status / reset (archive, never wipe)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jevlab.budget import reset_archive, status


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--reset-confirm", action="store_true", help="Archive current ledger and start fresh")
    args = ap.parse_args()
    if args.reset_confirm:
        dest = reset_archive()
        print(f"Archived ledger -> {dest}; starting fresh (history kept).")
        return
    st = status()
    if "error" in st:
        print(f"ERROR: {st['error']}")
        sys.exit(1)
    print(f"spent ${st['spent_usd']:.4f} / cap ${st['cap_usd']:.2f} "
          f"(remaining ${st['remaining_usd']:.4f}, {st['calls']} calls, "
          f"{st['spent_tokens']} tok + {st['reserved_tokens']} reserved)")


if __name__ == "__main__":
    main()
