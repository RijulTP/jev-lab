"""Copy-as-cURL/Python snippet for the current request (article-friendly)."""
from __future__ import annotations

import json


def as_curl(model: str, state, questions: dict) -> str:
    body = json.dumps({"model": model, "state": state, "questions": questions}, indent=2)
    return (
        "curl -X POST https://api.typesafe.ai/v1/systemone \\\n"
        '  -H "Authorization: Bearer $TYPESAFE_API_KEY" \\\n'
        '  -H "Content-Type: application/json" \\\n'
        f"  -d '{body}'"
    )


def as_python(model: str, state, questions: dict) -> str:
    return (
        "from typesafe_sdk import Choice, Noul, Score, TypeSafeClient\n\n"
        f"STATE = {state!r}\n"
        f"QUESTIONS = {questions!r}\n"
        f"MODEL = {model!r}\n\n"
        "with TypeSafeClient() as client:\n"
        "    response = client.system_one(state=STATE, questions=QUESTIONS, model=MODEL)\n"
        '    print(response.answers)\n'
    )
