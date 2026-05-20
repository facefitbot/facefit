from __future__ import annotations

import json
import re
from typing import Any


def parse_json_safely(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except json.JSONDecodeError:
            raw = fenced.group(1)

    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        candidate = raw[start : end + 1]
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise ValueError("AI вернул невалидный JSON, repair не смог восстановить структуру")

