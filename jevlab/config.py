"""Single source of truth for limits/prices. Reads jevlab/limits.yaml."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

_LIMITS_PATH = Path(__file__).with_name("limits.yaml")


def load_limits() -> dict:
    with open(_LIMITS_PATH) as f:
        return yaml.safe_load(f)


def staleness_days(limits: dict | None = None) -> int:
    lim = limits or load_limits()
    as_of = str(lim.get("as_of", ""))
    try:
        d = date.fromisoformat(as_of)
    except ValueError:
        return 10**9
    return (date.today() - d).days


def is_stale(limits: dict | None = None) -> bool:
    lim = limits or load_limits()
    return staleness_days(lim) > int(lim.get("staleness_warn_days", 30))


class QuestionValidationError(ValueError):
    pass


def validate_questions(questions: dict, limits: dict | None = None) -> None:
    """Enforce documented Choice/Score cardinality from limits.yaml."""
    lim = limits or load_limits()
    for name, q in questions.items():
        qd = q if isinstance(q, dict) else {
            "type": getattr(q, "type", ""),
            "criteria": getattr(q, "criteria", None),
        }
        t = str(qd.get("type", "")).lower()
        crit = qd.get("criteria")
        if t == "choice":
            n = len(crit) if isinstance(crit, dict) else 0
            if n > int(lim.get("choice_max_options", 255)):
                raise QuestionValidationError(
                    f"Question {name!r}: Choice has {n} options, max is "
                    f"{lim.get('choice_max_options')} (see {lim.get('sources', {}).get('choice_max')})."
                )
        elif t == "score":
            n = len(crit) if isinstance(crit, (list, tuple)) else 0
            lo, hi = int(lim.get("score_min_levels", 2)), int(lim.get("score_max_levels", 10))
            if not (lo <= n <= hi):
                raise QuestionValidationError(
                    f"Question {name!r}: Score has {n} levels, need {lo}-{hi} "
                    f"(see {lim.get('sources', {}).get('score_levels')})."
                )
