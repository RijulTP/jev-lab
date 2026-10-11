"""Fan-out benchmark CLI (thin wrapper over jevlab/bench.py)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("bench: use the Fan-out tab (live) for the interleaved benchmark, or")
print("`make record RECORD_ARGS='--force'` for recordings. See jevlab/bench.py.")
