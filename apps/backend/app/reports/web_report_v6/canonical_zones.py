from __future__ import annotations

import re
from typing import Any


CANONICAL_ZONES: dict[str, dict[str, Any]] = {
    "upper_eyelid": {"number": 1, "name": "Нависшее веко"},
    "under_eye_puffiness": {"number": 2, "name": "Отечность в зоне глаз"},
    "midface": {"number": 3, "name": "Средняя треть лица"},
    "forehead": {"number": 4, "name": "Лоб"},
    "glabella": {"number": 5, "name": "Межбровье"},
    "jawline": {"number": 6, "name": "Нижняя треть / овал лица"},
}

STATUS_MAP = {
    "green": "good",
    "good": "good",
    "strong": "good",
    "все хорошо": "good",
    "всё хорошо": "good",
    "yellow": "attention",
    "orange": "attention",
    "attention": "attention",
    "active_focus": "attention",
    "зона внимания": "attention",
    "red": "priority",
    "priority": "priority",
    "приоритет": "priority",
}

ZONE_ALIASES: tuple[tuple[str, str], ...] = (
    (r"\bверхн\w*\s+век|\bнависш\w*\s+век|\bобласть\s+глаз\s*/\s*веки", "upper_eyelid"),
    (r"\bпод\s+глаз|\bзон[аы]\s+глаз|\bот[её]чн\w*\s+.*глаз|\bнососл[её]з", "under_eye_puffiness"),
    (r"\bсредн\w*\s+треть|\bщ[её]к|\bскул|\bносогуб", "midface"),
    (r"\bлоб\b|\bфронталь", "forehead"),
    (r"\bмежбров|\bпереносиц", "glabella"),
    (r"\bовал|\bнижн\w*\s+треть|\bподбород|\bчелюст|\bбрыл|\bоколо-?ротов|\bуголк\w*\s+рта", "jawline"),
)

DEFAULT_ANCHORS = {
    "upper_eyelid": {"x": 50, "y": 30},
    "under_eye_puffiness": {"x": 50, "y": 41},
    "midface": {"x": 58, "y": 52},
    "forehead": {"x": 50, "y": 18},
    "glabella": {"x": 50, "y": 34},
    "jawline": {"x": 52, "y": 75},
}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _status(value: Any, color: Any = None) -> str:
    raw = _clean(value).lower()
    color_raw = _clean(color).lower()
    return STATUS_MAP.get(raw) or STATUS_MAP.get(color_raw) or "attention"


def canonical_key_from_zone(zone: dict[str, Any]) -> str | None:
    explicit = _clean(zone.get("key") or zone.get("zone_key") or zone.get("zone_id")).lower()
    if explicit in CANONICAL_ZONES:
        return explicit
    haystack = " ".join(
        _clean(zone.get(key)).lower()
        for key in ("name", "title", "label", "id", "zone_id", "meaning", "short_comment", "recommended_focus")
        if zone.get(key) is not None
    )
    for pattern, key in ZONE_ALIASES:
        if re.search(pattern, haystack, flags=re.IGNORECASE):
            return key
    number = zone.get("number")
    try:
        number_int = int(number)
    except (TypeError, ValueError):
        number_int = 0
    for key, item in CANONICAL_ZONES.items():
        if item["number"] == number_int:
            return key
    return None


def normalize_canonical_zones(input_zones: Any) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    raw_zones = input_zones if isinstance(input_zones, list) else []
    result: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    seen_numbers: set[int] = set()

    for raw in raw_zones:
        if not isinstance(raw, dict):
            continue
        key = canonical_key_from_zone(raw)
        if not key:
            warnings.append(f"unknown_zone: {_clean(raw.get('title') or raw.get('name') or raw.get('label'))}")
            continue
        canonical = CANONICAL_ZONES[key]
        number = int(canonical["number"])
        if key in seen_keys or number in seen_numbers:
            warnings.append(f"duplicate_zone_skipped: {key}")
            continue
        seen_keys.add(key)
        seen_numbers.add(number)
        anchor = raw.get("anchor") if isinstance(raw.get("anchor"), dict) else {}
        x = anchor.get("x", raw.get("cx", DEFAULT_ANCHORS[key]["x"]))
        y = anchor.get("y", raw.get("cy", DEFAULT_ANCHORS[key]["y"]))
        try:
            x = max(0, min(100, int(float(x))))
            y = max(0, min(100, int(float(y))))
        except (TypeError, ValueError):
            x, y = DEFAULT_ANCHORS[key]["x"], DEFAULT_ANCHORS[key]["y"]
        source_text = _clean(
            raw.get("simple_explanation")
            or raw.get("meaning")
            or raw.get("short_comment")
            or raw.get("description")
            or raw.get("what_is_visible")
        )
        benefit = _clean(raw.get("benefit") or raw.get("care_priority") or raw.get("recommended_focus") or raw.get("what_to_do"))
        result.append(
            {
                "number": number,
                "key": key,
                "name": canonical["name"],
                "status": _status(raw.get("status"), raw.get("color")),
                "simple_explanation": source_text,
                "benefit": benefit,
                "recommendation": benefit,
                "anchor": {"x": x, "y": y},
                "source_name": _clean(raw.get("title") or raw.get("name") or raw.get("label")),
            }
        )

    for key, canonical in CANONICAL_ZONES.items():
        number = int(canonical["number"])
        if key in seen_keys or number in seen_numbers:
            continue
        result.append(
            {
                "number": number,
                "key": key,
                "name": canonical["name"],
                "status": "good",
                "simple_explanation": "",
                "benefit": "",
                "recommendation": "",
                "anchor": DEFAULT_ANCHORS[key],
                "source_name": canonical["name"],
                "auto_filled": True,
            }
        )
        warnings.append(f"zone_auto_filled: {key}")

    result.sort(key=lambda item: item["number"])
    if len(result) > 6:
        warnings.append("zones_limited_to_6")
        result = result[:6]
    return result, warnings


def validate_zone_map_consistency(zone_map: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    zones = zone_map.get("zones") if isinstance(zone_map.get("zones"), list) else []
    numbers: set[int] = set()
    keys: set[str] = set()

    if zone_map.get("image_url") and not zones:
        errors.append("image_url_exists_but_zones_empty")
    for zone in zones:
        if not isinstance(zone, dict):
            errors.append("zone_is_not_object")
            continue
        key = zone.get("key")
        number = zone.get("number")
        if key not in CANONICAL_ZONES:
            errors.append(f"unknown_zone_key: {key}")
            continue
        canonical = CANONICAL_ZONES[key]
        if zone.get("name") != canonical["name"]:
            errors.append(f"zone_name_mismatch: {key}")
        if number != canonical["number"]:
            errors.append(f"zone_number_mismatch: {key}")
        if number in numbers:
            errors.append(f"duplicate_zone_number: {number}")
        if key in keys:
            errors.append(f"duplicate_zone_key: {key}")
        if zone.get("status") not in {"good", "attention", "priority"}:
            errors.append(f"wrong_zone_status: {key}")
        numbers.add(number)
        keys.add(key)
        if zone.get("source_name") and zone["source_name"] != canonical["name"]:
            warnings.append(f"mapped_old_zone_name: {zone['source_name']} -> {canonical['name']}")

    return {"passed": not errors, "errors": errors, "warnings": warnings}
