from __future__ import annotations

import re
from typing import Any

_AGE_PHRASE_RE = re.compile(r"\b(\d{1,3})\s*(?:лета|лет|года|год)\b", re.IGNORECASE)


def russian_year_word(value: int | str) -> str:
    number = abs(int(value))
    if 11 <= number % 100 <= 14:
        return "лет"
    if number % 10 == 1:
        return "год"
    if 2 <= number % 10 <= 4:
        return "года"
    return "лет"


def format_years(value: int | str) -> str:
    return f"{int(value)} {russian_year_word(value)}"


def normalize_russian_age_phrases(value: Any) -> str:
    text = "" if value is None else str(value)

    def replace(match: re.Match[str]) -> str:
        number = int(match.group(1))
        return format_years(number)

    return _AGE_PHRASE_RE.sub(replace, text)
