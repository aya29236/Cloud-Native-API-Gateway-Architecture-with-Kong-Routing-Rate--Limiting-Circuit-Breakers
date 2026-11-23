"""Load committed 18-question AI3 evaluation set."""

import json
from pathlib import Path
from typing import Any


EVAL_PATH = Path(__file__).with_name("eval_questions.json")


def load_eval_questions() -> list[dict[str, Any]]:
    return json.loads(EVAL_PATH.read_text(encoding="utf-8"))
