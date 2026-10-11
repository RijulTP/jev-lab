"""Dataset loaders with tune/test split.

Labels MUST be written before any Jev run; never adjust after seeing output.
Tune (100) for thresholds, test (50) for final numbers. See data/LABEL_NOTES.md.
"""
from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TUNE_SPLIT = 100


def load_jsonl(name: str) -> list[dict]:
    p = DATA_DIR / name
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def load_split(name: str, split: str) -> list[dict]:
    rows = load_jsonl(name)
    if split == "tune":
        return rows[:TUNE_SPLIT]
    if split == "test":
        return rows[TUNE_SPLIT:]
    raise ValueError("split must be 'tune' or 'test'")
