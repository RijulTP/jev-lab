"""Terminal version of the Playground demo. Demo mode uses presets; live mode allows custom state."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from jevlab.cache import CacheMiss, load_recording
from jevlab.client import JevError, decide


def main() -> None:
    from ui.tabs.playground import PRESETS

    live = bool(os.getenv("TYPESAFE_API_KEY"))
    print(f"Mode: {'LIVE' if live else 'DEMO'}")
    for i, p in enumerate(PRESETS):
        print(f"  [{i}] {p['name']}")
    idx = int(input("Pick preset [0]: ") or "0")
    preset = PRESETS[idx]
    model = os.getenv("JEV_MODEL", "jev-latest")
    try:
        if live:
            from typesafe_sdk import Choice, Noul, Score

            def to_sdk(plain):
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

            result = decide(preset["state"], to_sdk(preset["questions"]), model=model)
        else:
            result = load_recording(model, preset["state"], preset["questions"])
        print(json.dumps(result.raw, indent=2))
        print(f"latency={result.latency_ms:.0f}ms input_tokens={result.input_tokens}")
        if result.recorded_at:
            print(f"(recorded {result.recorded_at})")
    except (CacheMiss, JevError) as e:
        print(f"ERROR: {e}")


if __name__ == "__main__":
    main()
