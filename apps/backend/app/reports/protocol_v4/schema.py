from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Status = Literal["good", "attention", "priority"]
Shape = Literal["forehead", "glabella", "eyes", "nasolabial", "cheeks", "jawline", "chin", "neck", "puffiness"]

LABEL_LIMIT = 14
MAIN_FOCUS_LIMIT = 18
SUMMARY_LIMIT = 78
MAIN_CONCLUSION_LIMIT = 92
BULLET_LIMIT = 55
BENEFIT_CHIP_LIMIT = 24
FORECAST_LIMIT = 38

ZONE_LABEL_ALIASES = {
    "область глаз / веки": "Глаза",
    "область глаз и век": "Глаза",
    "нависшее веко / мешки под глазами": "Глаза",
    "носогубная зона": "Носогубка",
    "носогубные складки": "Носогубка",
    "потеря овала / брыли": "Овал",
    "овал лица": "Овал",
    "второй подбородок": "Подбородок",
    "зона отечности": "Отёчность",
    "отечность и усталый вид": "Отёчность",
    "отёчность и усталый вид": "Отёчность",
    "межбровная зона": "Межбровка",
    "межбровная морщина": "Межбровка",
}

DEFAULT_ZONES: list[dict[str, Any]] = [
    {"number": 1, "label": "Лоб", "status": "good", "shape": "forehead"},
    {"number": 2, "label": "Межбровка", "status": "attention", "shape": "glabella"},
    {"number": 3, "label": "Глаза", "status": "priority", "shape": "eyes"},
    {"number": 4, "label": "Носогубка", "status": "attention", "shape": "nasolabial"},
    {"number": 5, "label": "Скулы", "status": "good", "shape": "cheeks"},
    {"number": 6, "label": "Овал", "status": "priority", "shape": "jawline"},
    {"number": 7, "label": "Подбородок", "status": "attention", "shape": "chin"},
    {"number": 8, "label": "Шея", "status": "attention", "shape": "neck"},
]


def _clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"[*_`#>]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _replace_zone_label(label: Any) -> str:
    cleaned = _clean_text(label)
    return ZONE_LABEL_ALIASES.get(cleaned.lower(), cleaned)


def _shorten_text(text: Any, max_chars: int, fallback: str) -> str:
    cleaned = _replace_zone_label(text) or fallback
    if len(cleaned) <= max_chars:
        return cleaned

    for separator in [". ", "; ", ": ", ", ", " — ", " - "]:
        head = cleaned.split(separator, 1)[0].strip(" .,:;—-")
        if 8 <= len(head) <= max_chars:
            return head

    words: list[str] = []
    for word in cleaned.split():
        candidate = " ".join([*words, word])
        if len(candidate) > max_chars:
            break
        words.append(word)
    return " ".join(words).strip(" .,:;—-") or fallback[:max_chars].strip()


def _shape_for_label(label: Any, fallback: str = "forehead") -> str:
    normalized = _replace_zone_label(label).lower()
    if "лоб" in normalized:
        return "forehead"
    if "меж" in normalized:
        return "glabella"
    if "глаз" in normalized or "век" in normalized:
        return "eyes"
    if "носог" in normalized:
        return "nasolabial"
    if "скул" in normalized:
        return "cheeks"
    if "овал" in normalized or "бры" in normalized:
        return "jawline"
    if "подбор" in normalized:
        return "chin"
    if "ше" in normalized:
        return "neck"
    if "отеч" in normalized or "отёч" in normalized:
        return "puffiness"
    return fallback


def _status_from_zone(zone: dict[str, Any]) -> str:
    status = _clean_text(zone.get("status")).lower()
    color = _clean_text(zone.get("color")).lower()
    if status in {"good", "attention", "priority"}:
        return status
    if color == "green":
        return "good"
    if color == "red":
        return "priority"
    return "attention"


def _limited_list(items: Any, limit: int, max_chars: int, fallback_items: list[str]) -> list[str]:
    source = items if isinstance(items, list) else []
    result = [_shorten_text(item, max_chars, fallback_items[0]) for item in source if _clean_text(item)]
    result = result[:limit]
    for fallback in fallback_items:
        if len(result) >= limit:
            break
        if fallback not in result:
            result.append(_shorten_text(fallback, max_chars, fallback))
    return result[:limit]


def _short_benefit(text: Any, fallback: str) -> str:
    cleaned = _clean_text(text).lower()
    if "носог" in cleaned:
        return "Мягче носогубка"
    if "овал" in cleaned or "контур" in cleaned or "нижн" in cleaned:
        return "Чётче нижний контур"
    if "глаз" in cleaned or "взгляд" in cleaned or "век" in cleaned:
        return "Более открытый взгляд"
    if "отеч" in cleaned or "отёч" in cleaned or "лимф" in cleaned or "пастоз" in cleaned:
        return "Меньше отёчности"
    if "межбров" in cleaned:
        return "Мягче межбровка"
    if "тон" in cleaned or "кож" in cleaned or "микро" in cleaned:
        return "Лучше тон кожи"
    return _shorten_text(text, BENEFIT_CHIP_LIMIT, fallback)


def _short_forecast(text: Any, fallback: str) -> str:
    cleaned = _clean_text(text)
    lowered = cleaned.lower()
    if not cleaned:
        return fallback
    if "отеч" in lowered or "отёч" in lowered or "пастоз" in lowered:
        return "меньше отёчности"
    if "свеж" in lowered or "отдох" in lowered:
        return "свежее лицо"
    if "носог" in lowered:
        return "мягче носогубная зона"
    if "овал" in lowered or "контур" in lowered:
        return "устойчивее овал"
    if "тонус" in lowered or "кож" in lowered:
        return "ровнее тонус кожи"
    if re.fullmatch(r"через\s+\d+[\w\s–—-]*", lowered):
        return fallback
    return _shorten_text(cleaned, FORECAST_LIMIT, fallback)


class ProtocolZone(BaseModel):
    number: int
    label: str
    status: Status = "attention"
    shape: Shape = "forehead"

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        return _shorten_text(value, LABEL_LIMIT, "Зона")


class FaceMapCopy(BaseModel):
    title: str = "AI Face Scan"
    subtitle: str = "визуальный AI-разбор"
    main_focus: list[str] = Field(default_factory=lambda: ["Глаза", "Носогубка", "Овал"])
    zones: list[ProtocolZone] = Field(default_factory=lambda: [ProtocolZone(**zone) for zone in DEFAULT_ZONES])


class SummaryCopy(BaseModel):
    skin_age: str = "Кожа выглядит свежей, есть лёгкая усталость."
    skin_type: str = "Комбинированная, склонная к отёчности."
    aging_type: str = "Усталый тип с акцентом на глаза и овал."
    strengths: str = "Выразительные глаза, хороший потенциал овала."


class PlanCopy(BaseModel):
    causes: list[str] = Field(default_factory=lambda: ["Отёчность в зоне глаз", "Напряжение межбровки", "Снижение тонуса овала"])
    benefits: list[str] = Field(default_factory=lambda: ["Более открытый взгляд", "Мягче носогубная зона", "Чётче нижний контур"])
    forecast: list[str] = Field(default_factory=lambda: ["7–14 дней: меньше отёчности", "4–6 недель: свежее лицо", "8–12 недель: устойчивее овал"])


class ProtocolSlideCopy(BaseModel):
    face_map: FaceMapCopy = Field(default_factory=FaceMapCopy)
    summary: SummaryCopy = Field(default_factory=SummaryCopy)
    plan: PlanCopy = Field(default_factory=PlanCopy)


def normalize_protocol_slide_copy(protocol_slide_copy: dict[str, Any] | None) -> dict[str, Any]:
    raw = protocol_slide_copy if isinstance(protocol_slide_copy, dict) else {}
    face_map = raw.get("face_map") if isinstance(raw.get("face_map"), dict) else {}
    summary = raw.get("summary") if isinstance(raw.get("summary"), dict) else {}
    plan = raw.get("plan") if isinstance(raw.get("plan"), dict) else {}

    source_zones = face_map.get("zones") if isinstance(face_map.get("zones"), list) else []
    if not source_zones:
        source_zones = DEFAULT_ZONES

    normalized_zones: list[dict[str, Any]] = []
    used_shapes: set[str] = set()
    for index, zone in enumerate(source_zones[:8], start=1):
        if not isinstance(zone, dict):
            continue
        default = DEFAULT_ZONES[min(index - 1, len(DEFAULT_ZONES) - 1)]
        label = _shorten_text(zone.get("label") or zone.get("name"), LABEL_LIMIT, default["label"])
        shape = zone.get("shape") if zone.get("shape") else _shape_for_label(label, default["shape"])
        if shape not in {"forehead", "glabella", "eyes", "nasolabial", "cheeks", "jawline", "chin", "neck", "puffiness"}:
            shape = _shape_for_label(label, default["shape"])
        used_shapes.add(shape)
        normalized_zones.append(
            {
                "number": int(zone.get("number") or index),
                "label": label,
                "status": _status_from_zone(zone),
                "shape": shape,
            }
        )

    for default_zone in DEFAULT_ZONES:
        if len(normalized_zones) >= 8:
            break
        if default_zone["shape"] not in used_shapes:
            normalized_zones.append(default_zone)
            used_shapes.add(default_zone["shape"])

    copy = ProtocolSlideCopy(
        face_map=FaceMapCopy(
            title=_shorten_text(face_map.get("title"), 24, "AI Face Scan"),
            subtitle=_shorten_text(face_map.get("subtitle"), 28, "визуальный AI-разбор"),
            main_focus=_limited_list(face_map.get("main_focus"), 3, MAIN_FOCUS_LIMIT, ["Глаза", "Носогубка", "Овал"]),
            zones=[ProtocolZone(**zone) for zone in normalized_zones[:8]],
        ),
        summary=SummaryCopy(
            skin_age=_shorten_text(summary.get("skin_age"), SUMMARY_LIMIT, "Кожа выглядит свежей, есть лёгкая усталость."),
            skin_type=_shorten_text(summary.get("skin_type"), SUMMARY_LIMIT, "Комбинированная, склонная к отёчности."),
            aging_type=_shorten_text(summary.get("aging_type"), MAIN_CONCLUSION_LIMIT, "Усталый тип с акцентом на глаза и овал."),
            strengths=_shorten_text(summary.get("strengths"), SUMMARY_LIMIT, "Выразительные глаза, хороший потенциал овала."),
        ),
        plan=PlanCopy(
            causes=_limited_list(plan.get("causes"), 3, BULLET_LIMIT, ["Отёчность в зоне глаз", "Напряжение межбровки", "Снижение тонуса овала"]),
            benefits=[_short_benefit(item, fallback) for item, fallback in zip(
                _limited_list(plan.get("benefits"), 3, BULLET_LIMIT, ["Более открытый взгляд", "Мягче носогубная зона", "Чётче нижний контур"]),
                ["Более открытый взгляд", "Мягче носогубка", "Чётче нижний контур"],
                strict=False,
            )],
            forecast=[_short_forecast(item, fallback) for item, fallback in zip(
                _limited_list(plan.get("forecast"), 3, FORECAST_LIMIT, ["меньше отёчности", "свежее лицо", "устойчивее овал"]),
                ["меньше отёчности", "свежее лицо", "устойчивее овал"],
                strict=False,
            )],
        ),
    )
    return copy.model_dump()


def build_protocol_slide_copy_from_analysis(analysis_json: dict[str, Any], selected_problems: list[str] | None = None) -> dict[str, Any]:
    zones: list[dict[str, Any]] = []
    source_zones = analysis_json.get("zones") if isinstance(analysis_json.get("zones"), list) else []
    for index, zone in enumerate(source_zones[:8], start=1):
        if not isinstance(zone, dict):
            continue
        default = DEFAULT_ZONES[min(index - 1, len(DEFAULT_ZONES) - 1)]
        label = _replace_zone_label(zone.get("name") or zone.get("label") or default["label"])
        zones.append(
            {
                "number": zone.get("number") or index,
                "label": label,
                "status": _status_from_zone(zone),
                "shape": _shape_for_label(label, default["shape"]),
            }
        )

    focus = [_replace_zone_label(zone["label"]) for zone in zones if zone.get("status") == "priority"]
    focus.extend(_replace_zone_label(zone["label"]) for zone in zones if zone.get("status") == "attention")

    skin_age = analysis_json.get("skin_visual_age") if isinstance(analysis_json.get("skin_visual_age"), dict) else {}
    skin_type = analysis_json.get("skin_type") if isinstance(analysis_json.get("skin_type"), dict) else {}
    aging = analysis_json.get("face_type_and_aging_type") if isinstance(analysis_json.get("face_type_and_aging_type"), dict) else {}
    forecast = analysis_json.get("time_forecast") if isinstance(analysis_json.get("time_forecast"), dict) else {}

    return normalize_protocol_slide_copy(
        {
            "face_map": {
                "title": "AI Face Scan",
                "subtitle": "визуальный AI-разбор",
                "main_focus": focus[:3],
                "zones": zones or DEFAULT_ZONES,
            },
            "summary": {
                "skin_age": skin_age.get("explanation") or skin_age.get("estimated_range"),
                "skin_type": skin_type.get("type"),
                "aging_type": aging.get("aging_type") or aging.get("explanation"),
                "strengths": ", ".join((analysis_json.get("strengths") or [])[:2]),
            },
            "plan": {
                "causes": (analysis_json.get("causes") or [])[:3],
                "benefits": (analysis_json.get("facefitness_benefits") or [])[:3],
                "forecast": [
                    forecast.get("first_changes"),
                    forecast.get("visible_changes"),
                    forecast.get("stable_result"),
                ],
            },
        }
    )
