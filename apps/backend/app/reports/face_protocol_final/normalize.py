from __future__ import annotations

import re
from typing import Any

from app.reports.face_protocol_final.schema import DEFAULT_GROWTH_ZONES, DEFAULT_ZONES, EXAMPLE_PROTOCOL_COPY, ProtocolCopy

STATUS_VALUES = {"good", "attention", "priority"}

ALIASES = {
    "Область глаз / веки": "Зона глаз",
    "Нависшее веко / мешки под глазами": "Зона глаз",
    "Потеря овала / брыли": "Овал лица",
    "Второй подбородок": "Подбородок",
    "Отёчность и усталый вид": "Отёчность",
    "Отечность и усталый вид": "Отёчность",
    "Носогубные складки": "Носогубная зона",
    "Межбровная морщина": "Межбровье",
    "Межбровная зона": "Межбровье",
}


def _clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"[*_`#>]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _apply_aliases(text: Any) -> str:
    cleaned = _clean_text(text)
    lowered = cleaned.lower()
    for source, replacement in ALIASES.items():
        if lowered == source.lower():
            return replacement
    for source, replacement in ALIASES.items():
        cleaned = re.sub(re.escape(source), replacement, cleaned, flags=re.IGNORECASE)
    return cleaned


def _shorten_text(value: Any, max_chars: int, fallback: str) -> str:
    cleaned = _apply_aliases(value) or fallback
    if len(cleaned) <= max_chars:
        return cleaned

    for separator in (". ", "; ", ": ", ", ", " — ", " - ", " – "):
        head = cleaned.split(separator, 1)[0].strip(" .,:;—–-")
        if 8 <= len(head) <= max_chars:
            return _with_sentence_end(head, cleaned)

    words: list[str] = []
    for word in cleaned.split():
        candidate = " ".join([*words, word])
        if len(candidate) > max_chars:
            break
        words.append(word)
    shortened = " ".join(words).strip(" .,:;—–-")
    return _with_sentence_end(shortened or fallback[:max_chars].strip(" .,:;—–-"), cleaned)


def _with_sentence_end(text: str, source: str) -> str:
    if not text:
        return text
    if source.strip().endswith((".", "!", "?")) and not text.endswith((".", "!", "?")):
        return f"{text}."
    return text


def _status(value: Any) -> str:
    cleaned = _clean_text(value).lower()
    if cleaned in STATUS_VALUES:
        return cleaned
    if cleaned in {"green", "зелёный", "зеленый"}:
        return "good"
    if cleaned in {"red", "красный"}:
        return "priority"
    return "attention"


def _limited_text_list(items: Any, *, limit: int, max_chars: int, fallback: list[str]) -> list[str]:
    source = items if isinstance(items, list) else []
    result = [_shorten_text(item, max_chars, fallback[0]) for item in source if _clean_text(item)]
    result = result[:limit]
    for item in fallback:
        if len(result) >= limit:
            break
        shortened = _shorten_text(item, max_chars, item)
        if shortened not in result:
            result.append(shortened)
    return result[:limit]


def _normalize_zones(items: Any) -> list[dict[str, Any]]:
    source = items if isinstance(items, list) else []
    zones: list[dict[str, Any]] = []
    for index, raw_zone in enumerate(source[:6], start=1):
        if not isinstance(raw_zone, dict):
            continue
        default = DEFAULT_ZONES[min(index - 1, len(DEFAULT_ZONES) - 1)]
        zones.append(
            {
                "number": int(raw_zone.get("number") or index),
                "label": _shorten_text(raw_zone.get("label") or raw_zone.get("name"), 22, default["label"]),
                "status": _status(raw_zone.get("status") or raw_zone.get("color")),
            }
        )

    for default_zone in DEFAULT_ZONES:
        if len(zones) >= 6:
            break
        if not any(zone["label"].lower() == default_zone["label"].lower() for zone in zones):
            zones.append(default_zone.copy())
    return zones[:6]


def _normalize_growth_zones(items: Any, zones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source = items if isinstance(items, list) else []
    if not source:
        source = [
            {"label": zone["label"], "status": zone["status"]}
            for zone in zones
            if zone["status"] in {"priority", "attention"}
        ]
        source.extend(DEFAULT_GROWTH_ZONES)

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_zone in source:
        if len(result) >= 5:
            break
        if isinstance(raw_zone, dict):
            label = _shorten_text(raw_zone.get("label") or raw_zone.get("name"), 22, "Зона")
            status = _status(raw_zone.get("status") or raw_zone.get("color"))
        else:
            label = _shorten_text(raw_zone, 22, "Зона")
            status = "attention"
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append({"label": label, "status": status})

    for fallback in DEFAULT_GROWTH_ZONES:
        if len(result) >= 5:
            break
        key = fallback["label"].lower()
        if key not in seen:
            result.append(fallback.copy())
            seen.add(key)
    return result[:5]


def _score_value(value: Any) -> str:
    cleaned = _clean_text(value)
    if re.fullmatch(r"\d{1,3}/100", cleaned):
        return cleaned
    match = re.search(r"\d{1,3}", cleaned)
    if match:
        number = max(0, min(100, int(match.group(0))))
        return f"{number}/100"
    return "78/100"


def _insight_causes(personal_insight: dict[str, Any] | None) -> list[str]:
    insight = personal_insight if isinstance(personal_insight, dict) else {}
    items = insight.get("why_this_happens") if isinstance(insight.get("why_this_happens"), list) else []
    result: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        bullet = item.get("short_protocol_bullet")
        if not _clean_text(bullet):
            zone = _clean_text(item.get("zone"))
            visible = _clean_text(item.get("visible_sign"))
            mechanism = _clean_text(item.get("mechanism"))
            bullet = f"{zone}: {visible}. Причина — {mechanism}."
        if _clean_text(bullet):
            result.append(str(bullet))
    return result


def _insight_strengths(personal_insight: dict[str, Any] | None) -> list[str]:
    insight = personal_insight if isinstance(personal_insight, dict) else {}
    items = insight.get("strengths_explained") if isinstance(insight.get("strengths_explained"), list) else []
    result: list[str] = []
    for item in items:
        if isinstance(item, dict):
            bullet = item.get("short_protocol_bullet") or item.get("trait")
        else:
            bullet = item
        if _clean_text(bullet):
            result.append(str(bullet))
    return result


def _aging_type_key(value: Any) -> str:
    text = _clean_text(value).lower()
    if "муск" in text:
        return "muscular"
    if "деформа" in text or "отеч" in text or "отёч" in text:
        return "deformation"
    if "птоз" in text or "гравита" in text:
        return "ptosis"
    if "мелк" in text or "морщ" in text:
        return "wrinkled"
    if "устал" in text:
        return "tired"
    return "combined"


def _aging_forecast_fallback(aging_type: Any) -> list[str]:
    key = _aging_type_key(aging_type)
    if key == "muscular":
        return [
            "20–30 лет: возможны мимические линии лба и межбровья.",
            "30–40 лет: зажимы могут углублять носогубную зону.",
            "40+ лет: гипертонус фиксирует выражение напряжения.",
        ]
    if key in {"deformation", "ptosis"}:
        return [
            "20–30 лет: отёчность может делать лицо тяжелее к вечеру.",
            "30–40 лет: средняя треть постепенно смещается вниз.",
            "40+ лет: овал становится мягче без лимфодренажа и тонуса.",
        ]
    if key == "wrinkled":
        return [
            "20–30 лет: кожа быстрее реагирует на сухость и недосып.",
            "30–40 лет: вокруг глаз и губ может появляться мелкая сетка.",
            "40+ лет: объём уходит быстрее, чем чёткость овала.",
        ]
    if key == "tired":
        return [
            "20–30 лет: лицо свежее утром, но быстрее устаёт к вечеру.",
            "30–40 лет: тени под глазами и носогубная зона заметнее.",
            "40+ лет: уголки рта и нижняя треть требуют поддержки.",
        ]
    return [
        "20–30 лет: возможны мимические линии в активных зонах.",
        "30–40 лет: тонус средней и нижней трети может снижаться.",
        "40+ лет: овал и носогубная зона требуют регулярной поддержки.",
    ]


def _strong_base_fallback(analysis: dict[str, Any], insight: dict[str, Any]) -> str:
    strengths = _insight_strengths(insight) or analysis.get("strengths") or []
    text = " ".join(str(item) for item in strengths[:3]).lower()
    if any(word in text for word in ("скул", "челюст", "кост", "овал", "пропорц")):
        return "Сильная костная база и пропорции — хороший антиэйдж-фактор."
    if "глаз" in text or "взгляд" in text:
        return "Выразительный взгляд — ресурс, который быстро раскрывается через лимфодренаж."
    if "кож" in text or "плот" in text:
        return "Плотность кожи — сильная база для естественного визуального лифтинга."
    return "Ресурс лица уже есть: задача — раскрыть его через тонус, лимфу и расслабление."


def _why_intro_fallback(analysis: dict[str, Any], insight: dict[str, Any]) -> str:
    skin_type = analysis.get("skin_type") if isinstance(analysis.get("skin_type"), dict) else {}
    morphotype = insight.get("morphotype_story") if isinstance(insight.get("morphotype_story"), dict) else {}
    aging = analysis.get("face_type_and_aging_type") if isinstance(analysis.get("face_type_and_aging_type"), dict) else {}
    aging_type = morphotype.get("type") or aging.get("aging_type", "")
    key = _aging_type_key(aging_type)
    skin = _clean_text(skin_type.get("type"))
    skin_part = f"Ваш тип кожи — {skin}; " if skin else ""
    if key == "muscular":
        return skin_part + "мускульный сценарий держит овал, но без расслабления мышцы могут фиксировать заломы."
    if key in {"deformation", "ptosis"}:
        return skin_part + "отёчно-птозный сценарий выглядит молодо, но требует лимфодренажа, шеи и тонуса."
    if key == "wrinkled":
        return skin_part + "мелкоморщинистый сценарий требует мягкого тонуса, кровотока и бережного ухода."
    if key == "tired":
        return skin_part + "усталый сценарий быстро отражается во взгляде, тоне кожи и носогубной зоне."
    return skin_part + "комбинированный сценарий требует поддержки кожи, лимфы, шеи и мышечного тонуса."


def _why_outro_fallback(aging_type: Any) -> str:
    key = _aging_type_key(aging_type)
    if key == "muscular":
        return "Это не минус внешности: сильные мышцы — ресурс. Их нужно расслаблять и балансировать, чтобы лицо выглядело мягче."
    if key in {"deformation", "ptosis"}:
        return "Плотная кожа — плюс, но без оттока и тонуса лицо легче удерживает тяжесть. Регулярная работа раскрывает свежесть."
    if key == "wrinkled":
        return "Этот тип важно не перегружать: мягкая стимуляция и уход помогают коже выглядеть более живой и наполненной."
    if key == "tired":
        return "Хорошая новость: усталый тип быстро откликается на лимфу, шею и мягкий тонус — лицо выглядит отдохнувшим."
    return "Это не проблема, а логика вашего лица: если поддерживать отток, шею и тонус, черты выглядят легче и моложе."


def _morphotype_causes_fallback(aging_type: Any) -> list[str]:
    key = _aging_type_key(aging_type)
    if key == "muscular":
        return [
            "Сильная мимика держит лицо, но может закреплять межбровье и лоб.",
            "Жевательные зажимы делают нижнюю треть визуально строже.",
            "Без расслабления носогубная зона выглядит глубже, чем есть.",
            "Шея и осанка влияют на мягкость овала и выражение лица.",
        ]
    if key in {"deformation", "ptosis"}:
        return [
            "Плотная кожа хорошо держит лицо, но легче удерживает жидкость.",
            "Шея и осанка могут задерживать отток и давать пастозность.",
            "Нижняя треть требует тонуса, чтобы овал не выглядел тяжелее.",
            "Носогубная тень усиливается, когда средняя треть теряет опору.",
        ]
    if key == "wrinkled":
        return [
            "Тонкая кожа быстрее показывает сухость, стресс и недосып.",
            "Без мягкой стимуляции тканям не хватает кровотока и питания.",
            "Мимические зажимы быстрее превращают линии в видимую сетку.",
            "Овал может быть четким, но коже нужна регулярная поддержка.",
        ]
    if key == "tired":
        return [
            "Микроциркуляция влияет на то, насколько свежим выглядит взгляд.",
            "Носогубная зона заметнее, когда средняя треть теряет тонус.",
            "Недосып и стресс быстро отражаются в зоне глаз и уголках рта.",
            "Шея и лимфоток помогают убрать ощущение усталого лица.",
        ]
    return [
        "Кожа выглядит ресурсной, но ей нужна регулярная поддержка тонуса.",
        "Лимфоток влияет на свежесть взгляда и легкость нижней трети.",
        "Шея и осанка меняют то, насколько собранным выглядит овал.",
        "Мимические привычки могут усиливать тени и складки в активных зонах.",
    ]


def _benefits_outro_fallback(analysis: dict[str, Any], insight: dict[str, Any], aging_type: Any) -> str:
    strengths = " ".join(_insight_strengths(insight) or analysis.get("strengths") or []).lower()
    key = _aging_type_key(aging_type)
    if any(word in strengths for word in ("скул", "овал", "челюст", "ше")):
        return "Чёткие скулы, длинная шея и собранный овал дадут лицу естественный лифтинг-эффект."
    if "глаз" in strengths or "взгляд" in strengths:
        return "Открытый взгляд, лёгкая нижняя треть и свежая кожа визуально убирают несколько лет."
    if key in {"deformation", "ptosis"}:
        return "Когда уходит пастозность, скулы и овал читаются чётче — лицо выглядит легче и моложе."
    if key == "muscular":
        return "Расслабленные зажимы и мягкий тонус вернут чертам спокойствие, женственность и свежесть."
    if key == "wrinkled":
        return "Мягкий тонус и питание тканей дадут коже более живой, наполненный и дорогой вид."
    return "Свежий взгляд, ровный тон и собранный овал создают эффект естественного лифтинга."


def _benefits_fallback(aging_type: Any) -> list[str]:
    key = _aging_type_key(aging_type)
    if key == "muscular":
        return [
            "Расслабит жевательные и смягчит нижнюю треть.",
            "Откроет выражение лица через лоб и межбровье.",
            "Вернёт чертам спокойствие без потери тонуса.",
        ]
    if key in {"deformation", "ptosis"}:
        return [
            "Уменьшит пастозность и сделает лицо легче.",
            "Поддержит шею, овал и нижнюю треть.",
            "Проявит скулы и более чёткую линию челюсти.",
        ]
    if key == "wrinkled":
        return [
            "Улучшит питание кожи через мягкий кровоток.",
            "Сделает лицо более живым и наполненным.",
            "Поддержит овал без грубой нагрузки на кожу.",
        ]
    if key == "tired":
        return [
            "Откроет взгляд и снизит ощущение усталости.",
            "Смягчит носогубную зону через тонус средней трети.",
            "Вернёт лицу более отдохнувший и свежий вид.",
        ]
    return [
        "Снимет лишнюю отёчность и освежит взгляд.",
        "Поддержит шею, овал и нижнюю треть лица.",
        "Сделает черты более собранными и лёгкими.",
    ]


def normalize_protocol_copy(protocol_copy: dict[str, Any] | None) -> dict[str, Any]:
    raw = protocol_copy if isinstance(protocol_copy, dict) else {}
    base = EXAMPLE_PROTOCOL_COPY | raw

    skin_age = base.get("skin_age") if isinstance(base.get("skin_age"), dict) else {}
    skin_type = base.get("skin_type") if isinstance(base.get("skin_type"), dict) else {}
    face_aging = base.get("face_aging") if isinstance(base.get("face_aging"), dict) else {}

    zones = _normalize_zones(base.get("zones"))
    normalized = {
        "skin_age": {
            "value": _shorten_text(skin_age.get("value"), 4, "32"),
            "unit": _shorten_text(skin_age.get("unit"), 8, "лет"),
            "comment": _shorten_text(skin_age.get("comment"), 110, EXAMPLE_PROTOCOL_COPY["skin_age"]["comment"]),
            "score": _score_value(skin_age.get("score")),
        },
        "skin_type": {
            "title": _shorten_text(skin_type.get("title"), 42, EXAMPLE_PROTOCOL_COPY["skin_type"]["title"]),
            "bullets": _limited_text_list(
                skin_type.get("bullets"),
                limit=3,
                max_chars=75,
                fallback=EXAMPLE_PROTOCOL_COPY["skin_type"]["bullets"],
            ),
        },
        "face_aging": {
            "face_type": _shorten_text(face_aging.get("face_type"), 62, EXAMPLE_PROTOCOL_COPY["face_aging"]["face_type"]),
            "aging_type": _shorten_text(face_aging.get("aging_type"), 78, EXAMPLE_PROTOCOL_COPY["face_aging"]["aging_type"]),
            "bullets": _limited_text_list(
                face_aging.get("bullets"),
                limit=3,
                max_chars=95,
                fallback=EXAMPLE_PROTOCOL_COPY["face_aging"]["bullets"],
            ),
            "forecast": _limited_text_list(
                face_aging.get("forecast"),
                limit=3,
                max_chars=82,
                fallback=_aging_forecast_fallback(face_aging.get("aging_type")),
            ),
            "strong_base": _shorten_text(
                face_aging.get("strong_base"),
                110,
                EXAMPLE_PROTOCOL_COPY["face_aging"]["strong_base"],
            ),
        },
        "zones": zones,
        "causes": _limited_text_list(base.get("causes"), limit=4, max_chars=95, fallback=EXAMPLE_PROTOCOL_COPY["causes"]),
        "why_intro": _shorten_text(base.get("why_intro"), 180, EXAMPLE_PROTOCOL_COPY["why_intro"]),
        "why_outro": _shorten_text(base.get("why_outro"), 170, EXAMPLE_PROTOCOL_COPY["why_outro"]),
        "strengths": _limited_text_list(base.get("strengths"), limit=3, max_chars=75, fallback=EXAMPLE_PROTOCOL_COPY["strengths"]),
        "benefits": _limited_text_list(base.get("benefits"), limit=3, max_chars=75, fallback=EXAMPLE_PROTOCOL_COPY["benefits"]),
        "benefits_outro": _shorten_text(base.get("benefits_outro"), 130, EXAMPLE_PROTOCOL_COPY["benefits_outro"]),
        "forecast": _limited_text_list(base.get("forecast"), limit=3, max_chars=75, fallback=EXAMPLE_PROTOCOL_COPY["forecast"]),
        "growth_zones": _normalize_growth_zones(base.get("growth_zones"), zones),
        "final_summary": _shorten_text(base.get("final_summary"), 170, EXAMPLE_PROTOCOL_COPY["final_summary"]),
    }
    return ProtocolCopy.model_validate(normalized).model_dump()


def _first_number(text: Any, fallback: str = "32") -> str:
    match = re.search(r"\d{1,3}", _clean_text(text))
    return match.group(0) if match else fallback


def build_protocol_copy_from_analysis(
    analysis_json: dict[str, Any],
    selected_problems: list[str] | None = None,
    personal_insight_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    analysis = analysis_json if isinstance(analysis_json, dict) else {}
    selected = selected_problems or []
    insight = personal_insight_json if isinstance(personal_insight_json, dict) else {}

    skin_age = analysis.get("skin_visual_age") if isinstance(analysis.get("skin_visual_age"), dict) else {}
    skin_type = analysis.get("skin_type") if isinstance(analysis.get("skin_type"), dict) else {}
    aging = analysis.get("face_type_and_aging_type") if isinstance(analysis.get("face_type_and_aging_type"), dict) else {}
    forecast = analysis.get("time_forecast") if isinstance(analysis.get("time_forecast"), dict) else {}
    source_zones = analysis.get("zones") if isinstance(analysis.get("zones"), list) else []

    zones = [
        {
            "number": zone.get("number") or index,
            "label": zone.get("name") or zone.get("label"),
            "status": zone.get("status") or zone.get("color"),
        }
        for index, zone in enumerate(source_zones, start=1)
        if isinstance(zone, dict)
    ]

    features = []
    for key in ("features", "attention_points", "strengths"):
        value = skin_type.get(key)
        if isinstance(value, list):
            features.extend(value)

    growth = [
        {"label": problem, "status": "priority"}
        for problem in selected
    ]
    growth.extend({"label": zone.get("label"), "status": zone.get("status")} for zone in zones)

    insight_causes = _insight_causes(insight)
    insight_strengths = _insight_strengths(insight)
    morphotype = insight.get("morphotype_story") if isinstance(insight.get("morphotype_story"), dict) else {}
    strategy = insight.get("facefitness_strategy") if isinstance(insight.get("facefitness_strategy"), list) else []
    aging_type = morphotype.get("type") or aging.get("aging_type")

    return normalize_protocol_copy(
        {
            "skin_age": {
                "value": _first_number(skin_age.get("estimated_range"), "32"),
                "unit": "лет",
                "comment": skin_age.get("explanation"),
                "score": "78/100",
            },
            "skin_type": {
                "title": skin_type.get("type"),
                "bullets": features,
            },
            "face_aging": {
                "face_type": aging.get("face_type"),
                "aging_type": aging_type,
                "bullets": [
                    morphotype.get("why_this_type") or aging.get("explanation"),
                    morphotype.get("what_is_happening"),
                    morphotype.get("strategy"),
                    *[
                        f"{zone.get('label') or 'Зона'} — зона внимания."
                        for zone in zones
                        if zone.get("status") in {"priority", "attention", "red", "yellow"}
                    ],
                ],
                "forecast": _aging_forecast_fallback(aging_type),
                "strong_base": _strong_base_fallback(analysis, insight),
            },
            "zones": zones,
            "causes": insight_causes or _morphotype_causes_fallback(aging_type) or analysis.get("causes"),
            "why_intro": _why_intro_fallback(analysis, insight),
            "why_outro": _why_outro_fallback(aging_type),
            "strengths": insight_strengths or analysis.get("strengths"),
            "benefits": strategy or analysis.get("facefitness_benefits") or _benefits_fallback(aging_type),
            "benefits_outro": _benefits_outro_fallback(analysis, insight, aging_type),
            "forecast": [
                forecast.get("first_changes"),
                forecast.get("visible_changes"),
                forecast.get("stable_result"),
            ],
            "growth_zones": growth,
            "final_summary": insight.get("final_personal_summary") or insight.get("main_leverage_point") or analysis.get("summary"),
        }
    )
