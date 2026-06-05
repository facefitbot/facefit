from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

from app.ai.aging_knowledge import AGING_KNOWLEDGE, normalize_aging_classification
from app.ai.protocol_v4 import build_aging_type_display_name, mixed_combo_type_ids_from_payload, normalize_protocol_v4_shape
from app.api.serializers import report_view_model
from app.db.models import BotSettings, GeneratedReport
from app.reports.bella_web_report import (
    WEB_MAP_OBJECT_POSITION,
    _asset_url,
    _block,
    _block_bullets,
    _block_text,
    _clean,
    _client_age,
    _current_protocol,
    _date,
    _dict,
    _hero_conclusion_from_strengths,
    _human_join,
    _journal_data,
    _list,
    _protocol_zone_map,
    _strength_titles_from_protocol,
    _web_visual_age,
    _years_phrase,
    _zone_geometry,
)
from app.reports.web_report_v6.canonical_zones import normalize_canonical_zones, validate_zone_map_consistency
from app.storage.local import local_storage


WEB_REPORT_V6_VERSION = "bella_web_report_v6"
EARLY_PERIODS = ("7–14 дней", "4–6 недель", "8–12 недель")

FORBIDDEN_TOP_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bИсточник:\s*Telegram Bot\b", "telegram_source_label"),
    (r"\bстратеги[яию]\b", "strategy_word"),
    (r"\bмаршрут\b", "route_word"),
    (r"\bнейрон\w*\b", "neural_word"),
    (r"\bweb[-\s]?(протокол|report|отчет|отч[её]т)\b", "technical_web_word"),
    (r"\bведущие\s+механизмы\b", "leading_mechanisms_phrase"),
    (r"\bморфотип\w*\b", "morphotype_word"),
    (r"\bкомплексн(ый|ого|ому|ым)\s+подход\w*\b", "complex_approach_phrase"),
    (r"\bпастоз\w*\b", "pastosity_word"),
    (r"\bлимфостаз\w*\b", "lymphostasis_word"),
    (r"\bдеформаци[яию]\b", "deformation_word"),
    (r"\bптоз\b", "ptosis_word"),
    (r"\bпроблем\w*\b", "problem_word"),
    (r"\b[А-ЯA-Z]\s+[А-ЯA-Z]\s+[А-ЯA-Z]\b", "spaced_letters"),
)

SELLING_RESULT_MARKERS = (
    "свеже",
    "моложе",
    "сия",
    "ухож",
    "выразитель",
    "отдохнув",
    "собран",
    "красив",
    "курс",
    "фейсфитнес",
)

LANGUAGE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"\bпастозность\b", "легкая припухлость"),
    (r"\bпастозности\b", "легкой припухлости"),
    (r"\bпастозност\w*\b", "легкой припухлости"),
    (r"\bмикроциркуляци[яию]\b", "кровообращение"),
    (r"\bдеформаци(я|и|ю|ей|ям|ями|ях)\b", "изменения"),
    (r"\bптоз\w*\b", "опущение тканей"),
    (r"\bснижение\s+тонуса\b", "лицо выглядит менее собранным"),
    (r"\bлимфостаз\w*\b", "отечность"),
    (r"\bгипертонус\b", "перенапряжение мышц"),
    (r"\bдефект\b", "зона внимания"),
    (r"\bпроблемная\s+зона\b", "зона внимания"),
    (r"\bпроблема\b", "зона внимания"),
    (r"\bпроблемы\b", "зоны внимания"),
    (r"\bбрыли\b", "смягчение линии овала"),
    (r"\bмешки\s+под\s+глазами\b", "отечность в зоне глаз"),
)


def simplify_report_language(value: Any, *, limit: int | None = None) -> str:
    text = _clean(value)
    for pattern, replacement in LANGUAGE_REPLACEMENTS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(r"\s+([.,:;])", r"\1", text)
    replacements = [
        (r"\bВы будете\b", "Ты будешь"),
        (r"\bвы будете\b", "ты будешь"),
        (r"\bВы получите\b", "Ты получишь"),
        (r"\bвы получите\b", "ты получишь"),
        (r"\bВы заметите\b", "Ты заметишь"),
        (r"\bвы заметите\b", "ты заметишь"),
        (r"\bВы видите\b", "Ты видишь"),
        (r"\bвы видите\b", "ты видишь"),
        (r"\bВы смотрели\b", "Ты смотрела"),
        (r"\bвы смотрели\b", "ты смотрела"),
        (r"\bВы ощущаете\b", "Ты ощущаешь"),
        (r"\bвы ощущаете\b", "ты ощущаешь"),
        (r"\bВы расслаблены\b", "Ты расслаблена"),
        (r"\bвы расслаблены\b", "ты расслаблена"),
        (r"\bВы начнёте\b", "Ты начнёшь"),
        (r"\bвы начнёте\b", "ты начнёшь"),
        (r"\bВы начнете\b", "Ты начнёшь"),
        (r"\bвы начнете\b", "ты начнёшь"),
        (r"\bУ вас\b", "У тебя"),
        (r"\bу вас\b", "у тебя"),
        (r"\bВ вашем случае\b", "В твоём случае"),
        (r"\bв вашем случае\b", "в твоём случае"),
        (r"\b[Вв]аше лицо\b", "твоё лицо"),
        (r"\b[Вв]аш тип\b", "твой тип"),
        (r"\b[Вв]аш результат\b", "твой результат"),
        (r"\b[Вв]аш прогноз\b", "твой прогноз"),
        (r"\b[Вв]аши зоны\b", "твои зоны"),
        (r"\b[Вв]аши сильные стороны\b", "твои сильные стороны"),
        (r"\bвашего\b", "твоего"),
        (r"\bВашего\b", "Твоего"),
        (r"\bвашему\b", "твоему"),
        (r"\bВашему\b", "Твоему"),
        (r"\bвашей\b", "твоей"),
        (r"\bВашей\b", "Твоей"),
        (r"\bвашим\b", "твоим"),
        (r"\bВашим\b", "Твоим"),
        (r"\bвашими\b", "твоими"),
        (r"\bВашими\b", "Твоими"),
        (r"\bваших\b", "твоих"),
        (r"\bВаших\b", "Твоих"),
        (r"\bвашу\b", "твою"),
        (r"\bВашу\b", "Твою"),
        (r"\bваше\b", "твоё"),
        (r"\bВаше\b", "Твоё"),
        (r"\bваша\b", "твоя"),
        (r"\bВаша\b", "Твоя"),
        (r"\bваш\b", "твой"),
        (r"\bВаш\b", "Твой"),
        (r"\bваши\b", "твои"),
        (r"\bВаши\b", "Твои"),
        (r"\bвам\b", "тебе"),
        (r"\bВам\b", "Тебе"),
        (r"\bвас\b", "тебя"),
        (r"\bВас\b", "Тебя"),
        (r"\bвы\b", "ты"),
        (r"\bВы\b", "Ты"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    text = re.sub(r"\bлегкая легкая\b", "легкая", text, flags=re.IGNORECASE)
    text = re.sub(r"\bТип кожи:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s{2,}", " ", text).strip()
    if limit and len(text) > limit:
        words: list[str] = []
        for word in text.split():
            candidate = " ".join([*words, word])
            if len(candidate) > limit:
                break
            words.append(word)
        text = (" ".join(words) or text[:limit]).rstrip(" .,:;") + "."
    return text


def _with_name(name: str, text: Any, fallback: str = "") -> str:
    body = simplify_report_language(text or fallback)
    clean_name = _clean(name)
    if not clean_name or clean_name == "Гость" or not body:
        return body
    if body.lower().startswith(clean_name.lower()):
        return body
    body = body[:1].lower() + body[1:] if body else body
    return f"{clean_name}, {body}"


def _first_meaningful_sentence(value: Any, fallback: str) -> str:
    text = simplify_report_language(value)
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    return (parts[0].rstrip(" .") + ".") if parts else fallback


def _walk_strings(value: Any, path: str = "") -> list[tuple[str, str]]:
    if isinstance(value, str):
        return [(path, value)]
    if isinstance(value, dict):
        result: list[tuple[str, str]] = []
        for key, item in value.items():
            next_path = f"{path}.{key}" if path else str(key)
            result.extend(_walk_strings(item, next_path))
        return result
    if isinstance(value, list):
        result = []
        for index, item in enumerate(value):
            result.extend(_walk_strings(item, f"{path}[{index}]"))
        return result
    return []


def _first_sentence(value: Any, fallback: str, limit: int = 220) -> str:
    text = simplify_report_language(value)
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    result = parts[0] if parts else fallback
    return simplify_report_language(result.rstrip(" .") + ".", limit=limit)


def _items(value: Any, fallback: list[str], limit: int) -> list[str]:
    raw = value if isinstance(value, list) else []
    result: list[str] = []
    for item in raw:
        text = simplify_report_language(item, limit=210)
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    for item in fallback:
        if len(result) >= limit:
            break
        text = simplify_report_language(item, limit=210)
        if text and text not in result:
            result.append(text)
    return result[:limit]


def _is_face_protocol_ai_output(value: dict[str, Any]) -> bool:
    return {"bio_age", "skin_type", "aging_type", "zone_map", "changes_over_time"}.issubset(value.keys())


def _split_forecast_item(value: Any, fallback_period: str) -> dict[str, str]:
    text = _clean(value)
    for separator in (" — ", " – ", " - ", ": "):
        if separator in text:
            period, description = text.split(separator, 1)
            return {"period": _clean(period) or fallback_period, "text": _clean(description) or text}
    return {"period": fallback_period, "text": text}


def _protocol_ai_output_to_web_protocol(payload: dict[str, Any]) -> dict[str, Any]:
    bio_age = _dict(payload.get("bio_age"))
    skin_type = _dict(payload.get("skin_type"))
    aging = _dict(payload.get("aging_type"))
    zone_map = _dict(payload.get("zone_map"))
    strengths = _dict(payload.get("strengths"))
    changes = _dict(payload.get("changes_over_time"))
    facefitness = _dict(payload.get("facefitness"))
    forecast = _dict(payload.get("forecast"))
    summary = _dict(payload.get("summary"))
    meta = _dict(payload.get("meta"))

    classification = normalize_aging_classification(
        {"type_name": aging.get("name")},
        fallback_text=" ".join([_clean(aging.get("name")), _clean(aging.get("description"))]),
    )
    type_id = classification["type_id"]
    display_name = _clean(aging.get("name")) or classification["combined_label"] or classification["type_name"]
    combo_type_ids = classification.get("combo_type_ids") or []
    combo_type_names = classification.get("combo_type_names") or []

    raw_zones = zone_map.get("zones") if isinstance(zone_map.get("zones"), list) else []
    zones: list[dict[str, Any]] = []
    for index, raw in enumerate([item for item in raw_zones if isinstance(item, dict)][:6], start=1):
        status = _clean(raw.get("status")).lower()
        if status not in {"green", "yellow", "orange", "red"}:
            status = "yellow"
        zones.append(
            {
                "id": f"ai_zone_{raw.get('id') or index}",
                "number": int(raw.get("id") or index) if str(raw.get("id") or index).isdigit() else index,
                "title": _clean(raw.get("name")) or f"Зона {index}",
                "status": status,
                "meaning": _clean(raw.get("meaning") or raw.get("description") or changes.get("intro")),
                "anchor": raw.get("anchor") if isinstance(raw.get("anchor"), dict) else {},
                "shape": raw.get("shape") if isinstance(raw.get("shape"), dict) else {},
            }
        )

    forecast_periods = ["Через 2 недели", "Через 3–4 недели", "Через 6–8 недель"]
    raw_forecast_items = forecast.get("items") if isinstance(forecast.get("items"), list) else []
    forecast_items = [
        _split_forecast_item(item, forecast_periods[min(index, 2)])
        for index, item in enumerate(raw_forecast_items[:3])
    ]
    while len(forecast_items) < 3:
        forecast_items.append({"period": forecast_periods[len(forecast_items)], "text": ""})

    age_stages = [str(item) for item in changes.get("age_stages", []) if str(item or "").strip()] if isinstance(changes.get("age_stages"), list) else []
    growth_items = [zone["title"] for zone in zones if zone["status"] in {"yellow", "orange", "red"}]

    return {
        "protocol_version": "bella_face_protocol_v4",
        "client": {
            "name": "",
            "age": bio_age.get("passport_age") or bio_age.get("visual_age") or 30,
            "date": "",
        },
        "skin_visual_age": {
            "section_number": "01",
            "title": "Биологический возраст кожи",
            "passport_age": bio_age.get("passport_age") or bio_age.get("visual_age") or 30,
            "visual_age": bio_age.get("visual_age") or bio_age.get("passport_age") or 30,
            "skin_score": bio_age.get("skin_score"),
            "text": _clean(bio_age.get("description")),
        },
        "skin_type": {
            "section_number": "02",
            "title": "Тип кожи",
            "type_name": _clean(skin_type.get("name")),
            "text": _clean(skin_type.get("description")),
            "bullets": [_clean(skin_type.get("description"))],
        },
        "face_strengths": {
            "section_number": "03",
            "title": "Твои сильные стороны лица",
            "text": _clean(strengths.get("intro")),
            "bullets": [str(item) for item in strengths.get("items", []) if str(item or "").strip()] if isinstance(strengths.get("items"), list) else [],
        },
        "aging_type": {
            "section_number": "04",
            "title": "Тип старения",
            "type_id": type_id,
            "type_name": classification["type_name"],
            "display_name": display_name,
            "combo_type_ids": combo_type_ids,
            "combo_type_names": combo_type_names,
            "confidence": classification.get("confidence", "medium"),
            "text": _clean(aging.get("description")),
        },
        "future_changes": {
            "section_number": "05",
            "title": "Какие изменения будут со временем",
            "text": _clean(changes.get("intro")),
            "bullets": age_stages,
        },
        "age_changes": {
            "section_number": "06",
            "title": "Возрастная траектория",
            "text": "\n\n".join(age_stages),
        },
        "face_fitness_benefits": {
            "section_number": "07",
            "title": "Что даст фейс-фитнес",
            "text": _clean(facefitness.get("description")),
            "bullets": [str(item) for item in facefitness.get("items", []) if str(item or "").strip()] if isinstance(facefitness.get("items"), list) else [],
        },
        "time_forecast": {
            "section_number": "08",
            "title": "Прогноз по времени",
            "intro": _clean(forecast.get("intro")) or "Если ты начнёшь заниматься по нашей системе:",
            "items": forecast_items,
        },
        "growth_zones": {
            "section_number": "09",
            "title": "Зоны роста",
            "summary": _clean(facefitness.get("description")),
            "items": growth_items,
            "priorities": [{"priority": index + 1, "zone": zone, "why": _clean(changes.get("intro"))} for index, zone in enumerate(growth_items[:3])],
        },
        "zone_map": {"title": "Карта зон лица", "zones": zones},
        "final_summary": {
            "text": _clean(summary.get("text")),
            "quote": _clean(summary.get("quote")),
        },
        "meta": {
            "main_segment": meta.get("main_segment") or "general_freshness",
            "lead_temperature": meta.get("lead_temperature") or "warm",
        },
    }


def _protocol_candidates_from_sources(
    report: GeneratedReport | None,
    analysis_json: dict[str, Any],
    protocol_copy_json: dict[str, Any],
) -> list[dict[str, Any]]:
    if report and report.analysis:
        analysis = report.analysis
        analysis_json = analysis.analysis_json if isinstance(analysis.analysis_json, dict) else analysis_json
        protocol_copy_json = analysis.protocol_copy_json if isinstance(analysis.protocol_copy_json, dict) else protocol_copy_json
    return [
        _dict(protocol_copy_json.get("strict_blocks")),
        _dict(protocol_copy_json.get("face_protocol_ai_output")),
        _dict(protocol_copy_json.get("bella_protocol_v4")),
        _dict(analysis_json.get("face_protocol_ai_output")),
        _dict(analysis_json.get("bella_protocol_v4")),
        _dict(analysis_json.get("strict_blocks")),
        _dict(analysis_json.get("bella_protocol")),
        analysis_json if analysis_json.get("protocol_version") == "bella_face_protocol_v4" else {},
    ]


def _protocol_from_sources(report: GeneratedReport | None, analysis_json: dict[str, Any], protocol_copy_json: dict[str, Any]) -> dict[str, Any]:
    for candidate in _protocol_candidates_from_sources(report, analysis_json, protocol_copy_json):
        if candidate and _is_face_protocol_ai_output(candidate):
            return _protocol_ai_output_to_web_protocol(candidate)
        if candidate and all(key in candidate for key in ("skin_visual_age", "skin_type", "face_strengths", "aging_type")):
            try:
                return normalize_protocol_v4_shape(candidate)
            except Exception:
                return candidate
    return {}


def _component_name(component: str) -> str:
    return {
        "tired": "Усталый",
        "tired_mixed": "Усталый",
        "muscular": "Мускульный",
        "deformation_edema": "Деформационно-отечный",
        "fine_wrinkle": "Мелкоморщинистый",
    }.get(component, component)


COMPONENT_PUBLIC_COPY: dict[str, dict[str, str]] = {
    "muscular": {
        "short": "активная мимика и напряжение отдельных мышц",
        "characteristic": (
            "У этого сценария сильная сторона — лицо хорошо держит форму и овал. "
            "Но отдельные мышцы могут перенапрягаться: чаще всего лоб, межбровье, зона вокруг глаз и жевательная зона. "
            "Из-за этого выражение иногда выглядит строже, чем ты ощущаешь внутри."
        ),
        "future": (
            "Если не расслаблять эти зоны, мимические линии могут становиться глубже и заметнее даже в спокойном лице. "
            "Лоб и межбровье быстрее дают ощущение напряжения, а жевательная зона может делать черты тяжелее."
        ),
        "fitness": "Фейсфитнес поможет смягчить выражение, сделать взгляд спокойнее и сохранить четкость овала без ощущения зажатого лица.",
        "control": "Здесь важно не усиливать напряжение, а мягко расслаблять мышцы и возвращать лицу живую мимику.",
    },
    "deformation_edema": {
        "short": "склонность к отечности и утяжелению нижней трети",
        "characteristic": (
            "У этого сценария лицо может выглядеть мягким и женственным, но быстрее реагирует на задержку жидкости. "
            "Чаще всего это заметно под глазами, в нижней трети и по линии овала. "
            "Главная задача — помогать лицу выглядеть легче, свежее и собраннее."
        ),
        "future": (
            "Если не поддерживать отток жидкости и тонус тканей, утренняя припухлость может становиться заметнее. "
            "Зона под глазами быстрее дает усталый вид, а нижняя треть постепенно делает контур менее четким."
        ),
        "fitness": "Фейсфитнес поможет сделать лицо визуально легче: взгляд свежее, нижняя треть собраннее, овал аккуратнее.",
        "control": "Здесь особенно важны мягкая работа с шеей, осанкой, зоной глаз и нижней третью лица.",
    },
    "fine_wrinkle": {
        "short": "тонкая кожа, сухость и ранняя мелкая сетка",
        "characteristic": (
            "У этого сценария часто долго сохраняется аккуратный контур лица. "
            "Главная зона внимания — качество кожи: ей быстрее может не хватать влаги, мягкости и питания. "
            "Поэтому цель работы — сделать лицо более живым, свежим и наполненным."
        ),
        "future": (
            "Если не поддерживать кожу и мышцы, сухость может сильнее подчеркивать мелкие линии. "
            "Зона глаз, губы и щеки быстрее дают ощущение усталости, даже когда овал остается красивым."
        ),
        "fitness": "Фейсфитнес поможет улучшить питание тканей изнутри: кожа выглядит мягче, лицо живее, черты свежее.",
        "control": "Здесь важна бережная регулярность без сильного давления и растяжения кожи.",
    },
    "tired": {
        "short": "усталый вид к вечеру, зона глаз и носогубная зона",
        "characteristic": (
            "Это самый естественный сценарий: утром лицо может выглядеть свежим, а к вечеру быстрее уставать. "
            "Обычно сильнее считываются зона под глазами, носогубная зона и уголки рта. "
            "Хорошая новость — такой сценарий хорошо отвечает на регулярную мягкую работу."
        ),
        "future": (
            "Если не поддерживать лицо, усталый вид может становиться заметнее: взгляд выглядит тяжелее, "
            "носогубная зона глубже, уголки рта ниже. Лицо начинает чаще казаться невыспавшимся."
        ),
        "fitness": "Фейсфитнес поможет вернуть лицу свежесть: взгляд открывается, черты выглядят мягче, лицо меньше считывается уставшим.",
        "control": "Здесь важны мягкий тонус, зона глаз, носогубная зона и общий свежий вид лица.",
    },
}


def _component_public_key(component: str) -> str:
    if component == "tired_mixed":
        return "tired"
    if component in COMPONENT_PUBLIC_COPY:
        return component
    return "tired"


def _component_copy(component: str, field: str) -> str:
    return COMPONENT_PUBLIC_COPY[_component_public_key(component)].get(field, "")


def _component_effect(component: str) -> str:
    key = _component_public_key(component)
    return {
        "tired": "к вечеру взгляд быстрее выглядит уставшим, а носогубная зона становится заметнее",
        "deformation_edema": "зона под глазами и нижняя треть быстрее дают отечность и ощущение тяжести",
        "muscular": "отдельные мышцы лица могут перенапрягаться, из-за чего выражение выглядит строже",
        "fine_wrinkle": "коже быстрее не хватает влаги и мягкости, поэтому мелкие линии могут читаться раньше",
    }.get(key, COMPONENT_PUBLIC_COPY[key]["short"])


def _component_work_focus(component: str) -> str:
    key = _component_public_key(component)
    return {
        "tired": "вернуть лицу свежесть, открыть взгляд и смягчить носогубную зону",
        "deformation_edema": "сделать лицо визуально легче за счет работы с зоной глаз, шеей, овалом и нижней третью",
        "muscular": "расслабить перенапряженные зоны, чтобы выражение стало мягче",
        "fine_wrinkle": "улучшить ощущение питания кожи изнутри, чтобы лицо выглядело живее и мягче",
    }.get(key, COMPONENT_PUBLIC_COPY[key]["control"])


def _aging_public_characteristic(aging_id: str, aging_name: str, mixed_components: list[str]) -> str:
    if aging_id == "tired_mixed" and len(mixed_components) >= 2:
        names = " + ".join(_component_name(item) for item in mixed_components[:2])
        effects = [_component_effect(item) for item in mixed_components[:2]]
        return (
            f"Твой тип старения — комбинированный: {names}. "
            f"В нем соединяются два сценария: {effects[0]}; {effects[1]}. "
            "Сейчас это выражено мягко, поэтому курс может сработать красиво: освежить взгляд, облегчить контур и сохранить твою природную нежность."
        )
    return f"Твой тип старения — {aging_name}. {_component_copy(aging_id, 'characteristic')}"


def _aging_public_future(aging_id: str, mixed_components: list[str]) -> str:
    if aging_id == "tired_mixed" and len(mixed_components) >= 2:
        effects = [_component_effect(item) for item in mixed_components[:2]]
        return (
            f"Без регулярной поддержки постепенно усиливаются оба сценария: {effects[0]}; {effects[1]}. "
            "Сначала это выглядит спокойно — чуть больше усталости во взгляде, заметнее зона под глазами, мягче контур. "
            "Если начать сейчас, эти изменения проще удерживать в красивой, ухоженной форме."
        )
    return _component_copy(aging_id, "future")


def _aging_public_fitness(aging_id: str, mixed_components: list[str]) -> str:
    if aging_id == "tired_mixed" and len(mixed_components) >= 2:
        controls = [_component_work_focus(item) for item in mixed_components[:2]]
        return (
            f"Курс будет работать в двух направлениях. Первое — {controls[0]}. Второе — {controls[1]}. "
            "Визуально это дает понятный результат: взгляд легче, лицо меньше выглядит уставшим, а контур становится аккуратнее."
        )
    return _component_copy(aging_id, "fitness")


def _aging_public_control(aging_id: str, mixed_components: list[str]) -> str:
    if aging_id == "tired_mixed" and len(mixed_components) >= 2:
        controls = [_component_copy(item, "control") for item in mixed_components[:2]]
        return " ".join(controls)
    return _component_copy(aging_id, "control")


def _mixed_components(protocol: dict[str, Any], aging_id: str) -> list[str]:
    if aging_id != "tired_mixed":
        return []
    components = mixed_combo_type_ids_from_payload(protocol)
    normalized: list[str] = []
    for component in components:
        component = "tired" if component == "tired_mixed" else component
        if component in {"tired", "muscular", "deformation_edema", "fine_wrinkle"} and component not in normalized:
            normalized.append(component)
    if len(normalized) >= 2:
        return normalized[:2]
    text = " ".join(text for _, text in _walk_strings(protocol)).lower()
    markers = [
        ("muscular", ("межбров", "лоб", "жеватель", "перенапряж", "гипертонус", "мимик")),
        ("deformation_edema", ("отек", "отёк", "отеч", "отёч", "овал", "нижн", "шея", "жидк")),
        ("fine_wrinkle", ("сух", "тонк", "морщ", "сетк", "обезвож", "питан")),
        ("tired", ("устал", "носогуб", "носослез", "носослёз", "уголк", "свеж")),
    ]
    for key, words in markers:
        if key not in normalized and any(word in text for word in words):
            normalized.append(key)
    if len(normalized) < 2:
        normalized = ["tired", "deformation_edema"]
    return normalized[:2]


def _aging_name(aging_id: str, aging: dict[str, Any], mixed_components: list[str]) -> str:
    if aging_id == "tired_mixed" and len(mixed_components) >= 2:
        return "Комбинированный: " + " + ".join(_component_name(item) for item in mixed_components[:2])
    return simplify_report_language(aging.get("display_name") or aging.get("type_name") or build_aging_type_display_name(aging_id, []), limit=80)


def _kb_text_for_type(aging_id: str, mixed_components: list[str], field: str) -> str:
    if aging_id == "tired_mixed" and len(mixed_components) >= 2:
        parts = []
        for component in mixed_components[:2]:
            key = "tired_mixed" if component == "tired" else component
            parts.append(AGING_KNOWLEDGE.get(key, AGING_KNOWLEDGE["tired_mixed"]).get(field, ""))
        return " ".join(part for part in parts if part)
    return AGING_KNOWLEDGE.get(aging_id, AGING_KNOWLEDGE["tired_mixed"]).get(field, "")


def _zone_names(zones: list[dict[str, Any]], statuses: set[str] | None = None, limit: int = 4) -> list[str]:
    result: list[str] = []
    for zone in zones:
        if statuses and zone.get("status") not in statuses:
            continue
        name = simplify_report_language(zone.get("name"))
        if name and name not in result:
            result.append(name)
        if len(result) >= limit:
            break
    return result


def _zone_reading_phrase(zone_names: list[str], fallback: str = "зону глаз, овал и свежесть лица", *, case: str = "object") -> str:
    readable: list[str] = []
    object_replacements = {
        "отечность в зоне глаз": "зону под глазами",
        "зона под глазами": "зону под глазами",
        "средняя треть лица": "среднюю треть лица",
        "нижняя треть / овал лица": "овал",
        "овал лица / нижняя треть": "овал",
        "лоб": "лоб",
        "межбровье": "межбровье",
        "носогубная зона": "носогубную зону",
        "подбородок / около-ротовая зона": "область подбородка и уголков рта",
    }
    subject_replacements = {
        "отечность в зоне глаз": "зона под глазами",
        "зона под глазами": "зона под глазами",
        "средняя треть лица": "средняя треть лица",
        "нижняя треть / овал лица": "овал",
        "овал лица / нижняя треть": "овал",
        "лоб": "лоб",
        "межбровье": "межбровье",
        "носогубная зона": "носогубная зона",
        "подбородок / около-ротовая зона": "область подбородка и уголков рта",
    }
    replacements = subject_replacements if case == "subject" else object_replacements
    for name in zone_names:
        normalized = simplify_report_language(name).lower().strip(" .")
        phrase = replacements.get(normalized, normalized)
        if phrase and phrase not in readable:
            readable.append(phrase)
        if len(readable) >= 3:
            break
    return _human_join(readable, fallback)


def _feature_profile(strengths: dict[str, Any], final_summary_text: str, fallback_titles: list[str]) -> dict[str, Any]:
    raw_parts = [simplify_report_language(strengths.get("text"), limit=900), simplify_report_language(final_summary_text, limit=900)]
    for item in strengths.get("bullets") if isinstance(strengths.get("bullets"), list) else []:
        raw_parts.append(simplify_report_language(item, limit=220))
    raw = " ".join(part for part in raw_parts if part)
    lowered = raw.lower()

    features: list[str] = []
    if "светл" in lowered and ("глаз" in lowered or "взгляд" in lowered):
        features.append("светлые выразительные глаза")
    elif "глаз" in lowered or "взгляд" in lowered:
        features.append("выразительный взгляд")
    if "овал" in lowered:
        if "аккурат" in lowered:
            features.append("аккуратный овал")
        elif "мяг" in lowered:
            features.append("мягкий овал")
        else:
            features.append("красивая линия овала")
    if "скул" in lowered:
        features.append("скуловая опора")
    if "пропорц" in lowered or "симметр" in lowered:
        features.append("спокойные пропорции")
    if "губ" in lowered:
        features.append("мягкая линия губ")
    if "кож" in lowered and ("ровн" in lowered or "сия" in lowered or "ухож" in lowered):
        features.append("ровная ухоженная кожа")

    for title in fallback_titles:
        clean = simplify_report_language(title, limit=80).rstrip(" .")
        if not clean or re.search(r"от[её]ч|припух|устал|зона внимания|носослез|подглаз", clean, flags=re.IGNORECASE):
            continue
        clean_lower = clean.lower()
        if not any(clean_lower in item.lower() or item.lower() in clean_lower for item in features):
            features.append(clean.lower())
        if len(features) >= 5:
            break

    if not features:
        features = ["аккуратный овал", "выразительный взгляд", "мягкие пропорции"]

    # Keep a flattering, readable order: eyes → oval → cheekbones → proportions.
    order = ("глаз", "взгляд", "овал", "скул", "пропорц", "симметр", "губ", "кож")
    features = sorted(dict.fromkeys(features), key=lambda item: next((i for i, marker in enumerate(order) if marker in item), 99))
    phrase = _human_join(features[:4], "аккуратный овал, выразительный взгляд и мягкие пропорции")
    return {
        "items": features[:5],
        "phrase": phrase,
        "headline": "В лице уже есть мягкая, женственная база и хороший ресурс для естественного результата.",
        "procedure_value": (
            f"{phrase.capitalize()} — это та природная база, которую многие стараются подчеркнуть процедурами. "
            "В твоём случае задача курса не менять черты, а раскрыть их: сделать взгляд свежее, контур собраннее и общее впечатление моложе."
        ),
    }


def _zone_effect_phrases(zones: list[dict[str, Any]], limit: int = 3) -> list[str]:
    by_key = {
        "under_eye_puffiness": "зона под глазами быстрее дает ощущение усталости во взгляде",
        "upper_eyelid": "верхняя зона глаз влияет на открытость взгляда",
        "midface": "средняя треть просит мягкого тонуса, чтобы скулы читались яснее",
        "forehead": "лоб может делать выражение чуть более строгим",
        "glabella": "межбровье может добавлять лицу напряженное выражение",
        "jawline": "овал и нижняя треть отвечают за ощущение легкости контура",
        "nasolabial": "носогубная зона быстрее показывает усталость к вечеру",
    }
    result: list[str] = []
    for zone in zones:
        phrase = by_key.get(zone.get("key"))
        if phrase and phrase not in result:
            result.append(phrase)
        if len(result) >= limit:
            break
    return result


def _course_result_sentence(zones: list[dict[str, Any]], feature_phrase: str) -> str:
    keys = {zone.get("key") for zone in zones}
    parts: list[str] = []
    if {"under_eye_puffiness", "upper_eyelid"} & keys:
        parts.append("взгляд будет выглядеть легче и свежее")
    if {"midface", "nasolabial"} & keys:
        parts.append("скулы и средняя треть будут читаться выразительнее")
    if {"jawline"} & keys:
        parts.append("овал станет визуально собраннее")
    if {"forehead", "glabella"} & keys:
        parts.append("выражение лица станет мягче")
    if not parts:
        parts = ["лицо будет выглядеть свежее", "черты станут выразительнее"]
    return (
        f"В результате {', '.join(parts[:3])}. "
        "Это подчеркнет природную базу без ощущения, что черты нужно менять."
    )


def _zone_explanation(zone: dict[str, Any], aging_id: str) -> str:
    if zone.get("simple_explanation"):
        return simplify_report_language(zone["simple_explanation"], limit=160)
    key = zone.get("key")
    if zone.get("status") == "good":
        good_by_key = {
            "upper_eyelid": "Верхняя зона глаз выглядит спокойной и поддерживает открытость взгляда.",
            "under_eye_puffiness": "Зона под глазами сейчас не забирает главный фокус и легко поддерживается уходом.",
            "midface": "Средняя треть дает лицу мягкую опору и помогает скулам читаться аккуратно.",
            "forehead": "Лоб выглядит спокойным и не делает выражение лица жестким.",
            "glabella": "Межбровье не забирает внимание и сохраняет мягкость взгляда.",
            "jawline": "Овал и нижняя треть выглядят достаточно аккуратно и держат контур лица.",
        }
        return good_by_key.get(key, "Зона выглядит спокойно и поддерживает гармоничное впечатление лица.")
    by_key = {
        "upper_eyelid": "Верхняя зона глаз влияет на открытость взгляда и первое впечатление свежести.",
        "under_eye_puffiness": "Зона под глазами быстрее показывает недосып, усталость и задержку жидкости.",
        "midface": "Средняя треть влияет на то, насколько лицо выглядит собранным и отдохнувшим.",
        "forehead": "Лоб влияет на мягкость выражения и ощущение спокойного лица.",
        "glabella": "Межбровье может делать взгляд строже, если мышцы здесь перенапряжены.",
        "jawline": "Нижняя треть и овал отвечают за ощущение четкости и подтянутости лица.",
    }
    return by_key.get(key, "Эта зона влияет на общее впечатление свежести и собранности лица.")


def _zone_benefit(zone: dict[str, Any]) -> str:
    if zone.get("benefit"):
        return simplify_report_language(zone["benefit"], limit=140)
    if zone.get("status") == "good":
        by_key = {
            "upper_eyelid": "сохранить открытый, живой взгляд",
            "under_eye_puffiness": "поддержать свежесть взгляда",
            "midface": "подчеркнуть скулы и центральную часть лица",
            "forehead": "сохранить мягкое спокойное выражение",
            "glabella": "сохранить мягкость взгляда",
            "jawline": "поддержать аккуратный контур",
        }
        return by_key.get(zone.get("key"), "сохранить гармоничное впечатление лица")
    by_key = {
        "upper_eyelid": "взгляд будет выглядеть более открытым",
        "under_eye_puffiness": "лицо будет выглядеть более отдохнувшим",
        "midface": "скулы и центральная часть лица будут читаться выразительнее",
        "forehead": "выражение станет мягче и спокойнее",
        "glabella": "взгляд станет мягче, а лицо менее напряженным",
        "jawline": "контур будет выглядеть более собранным",
    }
    return by_key.get(zone.get("key"), "лицо будет выглядеть свежее и гармоничнее")


def _course_benefit_for_zone(zone: dict[str, Any]) -> dict[str, str]:
    key = zone.get("key")
    by_key = {
        "under_eye_puffiness": {
            "title": "Взгляд свежее",
            "text": "Зона под глазами выглядит легче, и лицо сразу воспринимается более отдохнувшим.",
            "ico": "eye",
        },
        "upper_eyelid": {
            "title": "Глаза открытее",
            "text": "Верхняя зона глаз выглядит мягче, взгляд становится более открытым и живым.",
            "ico": "eye",
        },
        "midface": {
            "title": "Скулы выразительнее",
            "text": "Средняя треть выглядит собраннее, поэтому скулы и центральная часть лица читаются красивее.",
            "ico": "sparkle",
        },
        "jawline": {
            "title": "Овал собраннее",
            "text": "Нижняя треть и линия овала выглядят аккуратнее, без ощущения тяжести.",
            "ico": "shape",
        },
        "forehead": {
            "title": "Выражение мягче",
            "text": "Лоб выглядит спокойнее, из-за этого лицо меньше считывается напряженным.",
            "ico": "feather",
        },
        "glabella": {
            "title": "Взгляд спокойнее",
            "text": "Межбровье выглядит мягче, и выражение лица становится более открытым.",
            "ico": "feather",
        },
        "nasolabial": {
            "title": "Лицо менее уставшее",
            "text": "Носогубная зона выглядит мягче, поэтому лицо меньше считывается уставшим к вечеру.",
            "ico": "shape",
        },
    }
    return by_key.get(
        key,
        {
            "title": "Черты гармоничнее",
            "text": f"{simplify_report_language(zone.get('name'), limit=80)} будет выглядеть спокойнее, а лицо — свежее.",
            "ico": "sparkle",
        },
    )


def _skin_type_title(skin_type: dict[str, Any]) -> str:
    title = simplify_report_language(skin_type.get("type_name") or skin_type.get("title"), limit=90)
    lowered = title.lower()
    if not title or "normal" in lowered or "нормаль" in lowered:
        return "Комбинированная, с ровной плотной базой"
    return title


def _skin_story(skin_type_name: str, skin_type: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    text = simplify_report_language(skin_type.get("text"), limit=240)
    skin_bullets = [str(item) for item in (skin_type.get("bullets") if isinstance(skin_type.get("bullets"), list) else [])[:3]]
    lowered = f"{skin_type_name} {text} {' '.join(skin_bullets)}".lower()
    if "комб" in lowered:
        type_sentence = "У тебя комбинированная кожа: центральная зона может быть активнее, а щекам часто нужно больше мягкости и увлажнения."
    elif "сух" in lowered or "обезвож" in lowered:
        type_sentence = "У тебя кожа со склонностью к сухости и обезвоженности: ей важно давать достаточно влаги и не пересушивать уходом."
    elif "чувств" in lowered:
        type_sentence = "У тебя чувствительная кожа: ей лучше подходит спокойный, бережный уход без резких экспериментов."
    elif "жир" in lowered:
        type_sentence = "У тебя кожа с более активной центральной зоной: ей важно мягкое очищение и хорошее увлажнение без перегруза."
    else:
        type_sentence = "По фото кожа выглядит ухоженной и достаточно ровной: это хорошая база для свежего, сияющего вида."

    if "обезвож" in lowered or "сух" in lowered:
        tendency = "ей важно избегать пересушивания и поддерживать влагу каждый день"
        potential = "при грамотном уходе кожа выглядит более ровной, мягкой и сияющей"
    elif "t-зон" in lowered or "т-зон" in lowered or "жир" in lowered:
        tendency = "центральная зона может быть активнее, поэтому важен баланс очищения и увлажнения"
        potential = "при правильном уходе тон выглядит ровнее, а кожа сохраняет свежесть"
    elif "чувств" in lowered:
        tendency = "ей важен спокойный уход без резких средств и частых экспериментов"
        potential = "при бережном подходе кожа выглядит ровнее, мягче и спокойнее"
    else:
        tendency = "она хорошо держит форму лица и благодарно отвечает на регулярный уход"
        potential = "при грамотном уходе можно получить более ровный тон, сияние и ухоженный вид"
    paragraph = f"{type_sentence} {tendency.capitalize()}. Тогда {potential}. Это как раз база для эффекта гладкой, ухоженной, сияющей кожи."
    cards = [
        {"title": "Кожа", "text": type_sentence, "ico": "drop"},
        {"title": "Что важно", "text": f"{tendency.capitalize()}, чтобы кожа выглядела спокойной и ухоженной.", "ico": "feather"},
        {"title": "Потенциал", "text": f"{potential.capitalize()}: ровнее тон, больше свежести и красивого сияния.", "ico": "sparkle"},
    ]
    return simplify_report_language(paragraph, limit=520), cards


def _zone_map_crop_url(protocol_image_path: str | None) -> str:
    if not protocol_image_path:
        return ""
    if protocol_image_path.startswith(("http://", "https://", "data:")):
        return protocol_image_path
    source = Path(local_storage.abs_path(protocol_image_path))
    if not source.exists():
        return ""
    # Preferred: the standalone face-map element screenshot the protocol renderer
    # saves alongside the page (face + colored zones + numbers, framed exactly as
    # in the PNG protocol). This is robust for any photo — no pixel guessing.
    element_shot = source.with_name(f"{source.stem}_zone_map_photo{source.suffix}")
    if element_shot.exists():
        return _asset_url(str(element_shot.relative_to(local_storage.root)))
    # Fallback for protocols rendered before the element screenshot existed:
    # crop the face-map region out of the composed PNG by fixed proportions.
    target = source.with_name(f"{source.stem}_zone_map_photo_crop_v5{source.suffix}")
    if target.exists() and target.stat().st_mtime >= source.stat().st_mtime:
        return _asset_url(str(target.relative_to(local_storage.root)))
    try:
        with Image.open(source) as image:
            width, height = image.size
            # The web report must reuse the exact face-map photo from the short
            # PNG protocol: same face crop, colored zones and black numbers.
            # The protocol PNG is always rendered at a fixed width (~1100px),
            # while its total height varies with the amount of text. The face-map
            # block sits at a fixed position driven by that width, so derive ALL
            # bounds from `width` (not `height`) — otherwise the crop drifts on
            # taller/shorter reports and slices off the top of the head or the
            # legend/zone-table underneath. Tuned to the full head down to just
            # above the legend.
            box = (
                max(0, int(width * 0.340)),
                max(0, int(width * 0.243)),
                min(width, int(width * 0.660)),
                min(height, int(width * 0.560)),
            )
            crop = image.crop(box)
            target.parent.mkdir(parents=True, exist_ok=True)
            crop.save(target)
    except Exception:
        return ""
    return _asset_url(str(target.relative_to(local_storage.root)))


def _early_changes(aging_id: str, mixed_components: list[str], priority_zones: list[str], main_focus: str) -> list[dict[str, str]]:
    if aging_id == "tired_mixed" and len(mixed_components) >= 2:
        return [
            {"period": "7–14 дней", "text": "В зеркале легче заметить более свежий взгляд и меньше утренней припухлости."},
            {"period": "4–6 недель", "text": "Средняя треть и овал выглядят собраннее, поэтому лицо кажется спокойнее и моложе."},
            {"period": "8–12 недель", "text": "Природные сильные стороны раскрываются ярче: взгляд, скулы и контур читаются чище."},
        ]
    by_type = {
        "muscular": [
            "Взгляд становится мягче, а лоб и межбровье выглядят спокойнее.",
            "Мимические линии меньше забирают внимание, лицо выглядит менее строгим.",
            "Четкий овал сохраняется, но черты становятся мягче и моложе.",
        ],
        "deformation_edema": [
            "Утром лицо выглядит легче, особенно в зоне глаз и нижней трети.",
            "Овал начинает читаться аккуратнее, без ощущения лишней тяжести.",
            "Лицо дольше сохраняет свежий вид, а контур выглядит собраннее.",
        ],
        "fine_wrinkle": [
            "Кожа выглядит мягче и ровнее, появляется ощущение более напитанного лица.",
            "Зона глаз и щеки меньше подчеркивают сухость и усталость.",
            "Лицо выглядит живее, а текстура кожи спокойнее и свежее.",
        ],
        "tired_mixed": [
            "Взгляд и общий тон лица выглядят свежее.",
            "Носогубная зона и уголки рта меньше дают усталое выражение.",
            "Лицо дольше выглядит отдохнувшим и собранным.",
        ],
    }
    texts = by_type.get(aging_id, by_type["tired_mixed"])
    return [{"period": period, "text": text} for period, text in zip(EARLY_PERIODS, texts)]


def _age_cards(client_age: int, aging_id: str) -> list[dict[str, Any]]:
    cards = [
        {"range": "20–30", "text": "Лучшее время закрепить свежесть: лицо уже красивое, а изменения еще легко удерживать.", "current": 20 <= client_age < 30},
        {"range": "30–40", "text": "Зона глаз, овал и выражение лица начинают быстрее показывать усталость без регулярности.", "current": 30 <= client_age < 40},
        {"range": "40–50", "text": "Регулярная работа помогает дольше сохранять мягкость черт, четкость контура и ухоженный вид.", "current": 40 <= client_age < 50},
        {"range": "50–60", "text": "Самый красивый результат дает спокойная постоянная поддержка: без силы, но с регулярностью.", "current": client_age >= 50},
    ]
    if not any(card["current"] for card in cards):
        cards[0]["current"] = True
    return cards


def _future_text(aging_id: str, mixed_components: list[str], zone_focus: str) -> tuple[str, str]:
    without = _aging_public_future(aging_id, mixed_components)
    with_work = _aging_public_fitness(aging_id, mixed_components)
    if zone_focus:
        with_work += f" В твоём случае акцент — {zone_focus.lower()}: через них быстрее всего возвращается свежесть."
    return simplify_report_language(without, limit=460), simplify_report_language(with_work, limit=540)


def _detail_items(
    *,
    visual_age: int,
    passport_age: int,
    skin_type_name: str,
    skin_story_text: str,
    strengths_text: str,
    feature_phrase: str,
    zone_effects: list[str],
    course_result: str,
    aging_name: str,
    aging_id: str,
    mixed_components: list[str],
    zones: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    zone_names = [zone["name"] for zone in zones[:3]]
    main_zones = _human_join(zone_names[:3], "зона глаз, овал и шея")
    morning_focus = _human_join(zone_names[:2], "зона глаз и шея")
    return [
        {
            "key": "01",
            "title": "Утренний старт на 5 минут",
            "body": f"Начинай день с мягкого дыхания, шеи и зоны {morning_focus.lower()}. Это помогает лицу быстрее проснуться, убрать ощущение тяжести и подготовить ткани к упражнениям без лишнего напряжения.",
            "list": ["1 минута спокойного дыхания", "2 минуты шея и плечи", "2 минуты мягкая работа с зоной глаз"],
        },
        {
            "key": "02",
            "title": "Основной фокус упражнений",
            "body": f"Главная работа идёт через {main_zones.lower()}. Сначала снимаем лишнее напряжение и поддерживаем отток, затем добавляем мягкий тонус, чтобы лицо выглядело свежее и собраннее.",
            "list": ["не давить сильно", "не тянуть кожу", "работать медленно и регулярно"],
        },
        {
            "key": "03",
            "title": "Вечернее расслабление",
            "body": "Вечером важнее не тренировать лицо на силу, а мягко снять накопленное напряжение. Особенно хорошо работают спокойные движения по лбу, межбровью, жевательной зоне и шее.",
            "list": ["3 минуты расслабления", "без активного растяжения", "после ухода или перед сном"],
        },
        {
            "key": "04",
            "title": "Уход, который поддержит результат",
            "body": skin_story_text,
            "list": ["мягкое очищение", "стабильное увлажнение", "без пересушивания и резких экспериментов"],
        },
        {
            "key": "05",
            "title": "Ритм на неделю",
            "body": "Лучше коротко, но регулярно: лицу важна последовательность, а не редкие длинные занятия. Для старта достаточно 4-5 практик в неделю и одного спокойного дня без активной нагрузки.",
            "list": ["4-5 раз в неделю", "10-15 минут", "один день мягкого восстановления"],
        },
        {
            "key": "06",
            "title": "Как понять, что ты идёшь верно",
            "body": f"Ориентир не в резком эффекте, а в том, что лицо постепенно выглядит спокойнее, легче и свежее. {course_result}",
            "list": ["меньше утренней тяжести", "мягче выражение лица", "контур читается аккуратнее"],
        },
    ]


def validate_web_report_quality(report_view_model: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if report_view_model.get("report_version") != WEB_REPORT_V6_VERSION:
        errors.append("wrong_report_version")
    if report_view_model.get("web_report_version") != WEB_REPORT_V6_VERSION:
        errors.append("wrong_web_report_version")
    if not _dict(report_view_model.get("hero")).get("personal_conclusion"):
        errors.append("missing_hero_compliment")
    if not _dict(report_view_model.get("story")).get("current_appearance"):
        errors.append("missing_story_current_appearance")
    zone_quality = validate_zone_map_consistency(_dict(report_view_model.get("zone_map")))
    errors.extend(zone_quality["errors"])
    warnings.extend(zone_quality["warnings"])
    benefits_text = " ".join(text for _, text in _walk_strings(report_view_model.get("benefits")))
    if "Замедление возрастных изменений" not in benefits_text:
        errors.append("missing_required_benefit_slowing_age_changes")
    early_items = _dict(report_view_model.get("early_changes")).get("items")
    periods = [item.get("period") for item in early_items] if isinstance(early_items, list) else []
    if periods != list(EARLY_PERIODS):
        errors.append(f"wrong_early_periods: {periods}")
    future = _dict(report_view_model.get("future"))
    if not future.get("without_work") or not future.get("with_work"):
        errors.append("missing_future_with_without")
    if not _dict(report_view_model.get("final_cta")).get("button_text"):
        errors.append("missing_final_cta")
    top_blocks = {
        "hero": report_view_model.get("hero"),
        "story": report_view_model.get("story"),
        "benefits": report_view_model.get("benefits"),
        "future": report_view_model.get("future"),
        "details": report_view_model.get("details"),
        "final_cta": report_view_model.get("final_cta"),
    }
    for path, text in _walk_strings(top_blocks):
        for pattern, label in FORBIDDEN_TOP_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                errors.append(f"forbidden_top_language: {label} at {path}")
                break
        if len(text) > 900:
            warnings.append(f"long_paragraph: {path}")
    visible_copy = " ".join(text.lower() for _, text in _walk_strings(top_blocks))
    if sum(1 for marker in SELLING_RESULT_MARKERS if marker in visible_copy) < 5:
        errors.append("weak_selling_result_language")
    if "курс" not in visible_copy and "фейсфитнес" not in visible_copy:
        errors.append("missing_course_sales_context")
    return {"version": WEB_REPORT_V6_VERSION, "passed": not errors, "errors": errors, "warnings": warnings}


def build_bella_web_report_v6_view_model(
    *,
    report: GeneratedReport | None = None,
    settings: BotSettings | None = None,
    analysis_json: dict[str, Any] | None = None,
    protocol_copy_json: dict[str, Any] | None = None,
    existing_deep_report: dict[str, Any] | None = None,
    zone_map: dict[str, Any] | None = None,
    face_protocol_image_url: str = "",
    original_photo_url: str = "",
    client: dict[str, Any] | None = None,
) -> dict[str, Any]:
    analysis = report.analysis if report else None
    source_analysis_json = analysis_json if isinstance(analysis_json, dict) else (analysis.analysis_json if analysis and isinstance(analysis.analysis_json, dict) else {})
    source_protocol_copy = protocol_copy_json if isinstance(protocol_copy_json, dict) else (analysis.protocol_copy_json if analysis and isinstance(analysis.protocol_copy_json, dict) else {})
    protocol = _protocol_from_sources(report, source_analysis_json, source_protocol_copy)

    if report:
        try:
            public_view = report_view_model(report, settings) if settings else {}
        except Exception:
            public_view = {}
    else:
        public_view = {}
    images = _dict(public_view.get("images"))
    before_asset = _dict(images.get("original_photo"))
    original_url = original_photo_url or _asset_url(before_asset.get("path") or before_asset.get("url") or (analysis.original_photo_path if analysis else None))

    client_block = _dict(protocol.get("client"))
    client_source = client if isinstance(client, dict) else {}
    lead_name = _clean(
        client_source.get("name")
        or client_block.get("name")
        or (analysis.lead.name if analysis and analysis.lead and analysis.lead.name else ""),
        "Гость",
    )
    client_age = int(client_source.get("age") or client_block.get("age") or (_client_age(report) if report else 30))
    report_date = _date(client_source.get("analysis_date") or client_source.get("date") or client_block.get("date") or (analysis.created_at if analysis else datetime.now()))

    skin_age = _block(protocol, "skin_visual_age")
    skin_type = _block(protocol, "skin_type")
    strengths = _block(protocol, "face_strengths")
    aging = _block(protocol, "aging_type")
    benefits = _block(protocol, "face_fitness_benefits")

    passport_age = int(skin_age.get("passport_age") or client_age)
    try:
        suggested_visual_age = int(skin_age.get("visual_age")) if skin_age.get("visual_age") is not None else None
    except (TypeError, ValueError):
        suggested_visual_age = None
    visual_age = _web_visual_age(passport_age, suggested_visual_age, report.id if report else None)

    aging_classification = normalize_aging_classification(aging)
    aging_id = aging_classification["type_id"]
    mixed_components = _mixed_components(protocol, aging_id)
    aging_name = _aging_name(aging_id, aging, mixed_components)

    geometry = _zone_geometry(report) if report else {}
    photo_protocol_data = _journal_data(report, original_url, geometry) if report else {}
    photo_zone_map = _dict(photo_protocol_data.get("zone_map"))
    source_zone_map = zone_map if isinstance(zone_map, dict) else (photo_zone_map if photo_zone_map else _protocol_zone_map(protocol))
    raw_zones = source_zone_map.get("zones") if isinstance(source_zone_map.get("zones"), list) else []
    canonical_zones, zone_warnings = normalize_canonical_zones(raw_zones)
    if not canonical_zones:
        canonical_zones, extra_warnings = normalize_canonical_zones(_block(protocol, "zone_map").get("zones"))
        zone_warnings.extend(extra_warnings)
    priority_zones = _zone_names(canonical_zones, statuses={"attention", "priority"}, limit=4)
    strong_zones = _zone_names(canonical_zones, statuses={"good"}, limit=3)
    main_focus = _human_join(priority_zones[:3], "зона глаз, овал и свежесть лица")
    raw_strength_titles = _strength_titles_from_protocol(protocol, 4)
    strength_titles = [
        simplify_report_language(item, limit=70).rstrip(".")
        for item in raw_strength_titles
        if item and not re.search(r"от[её]ч|припух|устал|зона внимания|носослез", str(item), flags=re.IGNORECASE)
    ][:4]
    if not strength_titles:
        strength_titles = strong_zones or ["форма лица", "взгляд", "пропорции"]
    final_summary_text = _block_text(protocol, "final_summary") or ""
    feature_profile = _feature_profile(strengths, final_summary_text, strength_titles)
    feature_phrase = feature_profile["phrase"]
    strong_focus = feature_phrase

    for zone in canonical_zones:
        zone["simple_explanation"] = _zone_explanation(zone, aging_id)
        zone["benefit"] = _zone_benefit(zone)
        zone["recommendation"] = zone["benefit"]

    skin_type_name = _skin_type_title(skin_type)
    skin_story_text, skin_cards = _skin_story(skin_type_name, skin_type)
    strengths_text = simplify_report_language(feature_profile["procedure_value"], limit=560)
    zone_focus_text = _human_join(priority_zones[:3], main_focus)
    zone_reading_object = _zone_reading_phrase(priority_zones[:3])
    zone_reading_subject = _zone_reading_phrase(priority_zones[:3], case="subject", fallback="зона глаз, овал и свежесть лица")
    priority_zone_cards = [zone for zone in canonical_zones if zone.get("status") in {"attention", "priority"}]
    zone_effects = _zone_effect_phrases(priority_zone_cards, limit=3)
    zone_effect_sentence = _human_join(zone_effects[:2], "зона глаз и овал быстрее дают ощущение усталости")
    course_result = _course_result_sentence(priority_zone_cards, feature_phrase)
    visual_reason = zone_effect_sentence
    hero_source = _block_text(protocol, "skin_visual_age")
    hero_conclusion = _with_name(
        lead_name,
        hero_source,
        (
            f"по фото первое впечатление мягкое и свежее. Визуально сейчас около {_years_phrase(visual_age)}: возраст добавляют не черты, "
            f"а то, что {visual_reason}. Если мягко поддержать эти зоны, лицо будет выглядеть легче, спокойнее и моложе."
        ),
    )
    current_text = _with_name(
        lead_name,
        "",
        (
            f"сейчас лучше всего начинать с зоны «{zone_reading_subject}». Именно она быстрее всего влияет на то, насколько лицо выглядит "
            "отдохнувшим в обычной жизни. Хорошая новость в том, что изменения пока мягкие, поэтому регулярная работа может дать очень естественный результат."
        ),
    )
    appearance_cards = [
        {
            "title": "Что добавляет возраст",
            "text": f"Сейчас лицо выглядит примерно на {_years_phrase(visual_age)}. Главная причина — {zone_effect_sentence}. Когда эти зоны спокойнее, лицо сразу выглядит моложе и легче.",
            "ico": "eye",
        },
        {"title": "Кожа", "text": skin_story_text, "ico": "drop"},
        {"title": "Сильные стороны", "text": strengths_text, "ico": "sparkle"},
    ]
    focus_text = (
        f"Начинаем с {zone_reading_subject}, потому что эти зоны сильнее всего влияют на первое впечатление. "
        "Когда они выглядят легче, взгляд становится свежее, черты мягче, а лицо воспринимается более отдохнувшим."
    )
    potential_items = [
        {"title": "Выглядеть свежее", "text": "Взгляд меньше считывается уставшим, лицо выглядит легче уже по первому впечатлению.", "ico": "eye"},
        {"title": "Раскрыть природную красоту", "text": "Курс помогает не менять черты, а вернуть лицу состояние отдыха, мягкости и живого тонуса.", "ico": "sparkle"},
        {"title": "Собрать контур", "text": "Овал и нижняя треть выглядят аккуратнее, поэтому лицо воспринимается моложе.", "ico": "shape"},
        {"title": "Начать в правильный момент", "text": "Пока изменения мягкие, их проще удержать и красиво направить регулярной работой.", "ico": "clock"},
    ]
    benefits_items = [_course_benefit_for_zone(zone) for zone in priority_zone_cards[:3]]
    benefits_items.extend(
        [
            {"title": "Черты выразительнее", "text": "Фейсфитнес помогает лицу выглядеть более живым: взгляд открывается, выражение становится мягче, контур читается спокойнее.", "ico": "sparkle"},
            {"title": "Кожа ухоженнее", "text": "Лицо выглядит ровнее и свежее, потому что уход и упражнения работают в одном направлении.", "ico": "drop"},
            {"title": "Замедление возрастных изменений", "text": "Регулярность помогает дольше сохранять молодость, свежесть и природную форму лица.", "ico": "clock"},
        ]
    )
    deduped_benefits: list[dict[str, str]] = []
    seen_benefits: set[str] = set()
    for item in benefits_items:
        key = re.sub(r"[^a-zа-яё0-9]+", " ", f"{item['title']} {item['text']}".lower()).strip()
        if key in seen_benefits:
            continue
        seen_benefits.add(key)
        deduped_benefits.append(item)
        if len(deduped_benefits) >= 5:
            break
    if not any(item["title"] == "Замедление возрастных изменений" for item in deduped_benefits):
        deduped_benefits[-1] = {"title": "Замедление возрастных изменений", "text": "Регулярная работа помогает дольше сохранять молодость, свежесть и природную форму лица.", "ico": "clock"}

    early_items = _early_changes(aging_id, mixed_components, priority_zones, main_focus)
    without_work, with_work = _future_text(aging_id, mixed_components, zone_reading_subject)

    cta_text = (settings.cta_text if settings else "") or "Получить персональную программу"
    cta_url = (settings.whatsapp_url or settings.telegram_url or settings.instagram_url) if settings else ""
    face_protocol_path = analysis.face_protocol_image_path if analysis else None
    face_protocol_url = face_protocol_image_url or _asset_url(face_protocol_path)
    zone_map_crop_url = _zone_map_crop_url(face_protocol_path)
    zone_map_photo_url = zone_map_crop_url or original_url
    zone_map_image_mode = "protocol_crop" if zone_map_crop_url else "overlay"
    zone_map_source = "png_protocol_zone_map_crop" if zone_map_crop_url else "photo_protocol_zone_overlay"

    # Optional side-profile photo + its AI read-out (jaw / oval / chin / neck).
    profile_block = _dict(source_analysis_json.get("profile"))
    profile_photo_url = _asset_url(analysis.profile_photo_path) if analysis and analysis.profile_photo_path else ""
    profile_view = (
        {
            "title": "Профиль · овал и шея",
            "image_url": profile_photo_url,
            "summary": simplify_report_language(profile_block.get("summary") or "", limit=400),
            "jawline": simplify_report_language(profile_block.get("jawline") or "", limit=400),
            "chin_neck": simplify_report_language(profile_block.get("chin_neck") or "", limit=400),
        }
        if (profile_photo_url and profile_block.get("usable"))
        else None
    )

    view_model: dict[str, Any] = {
        "report_version": WEB_REPORT_V6_VERSION,
        "web_report_version": WEB_REPORT_V6_VERSION,
        "report_id": f"BV-{report.id:04d}" if report and report.id else "BV-PREVIEW",
        "client": {"name": lead_name, "age": client_age, "analysis_date": report_date},
        "images": {
            "original_photo_url": original_url,
            "face_protocol_image_url": face_protocol_url,
            "zone_map_image_url": zone_map_photo_url,
            "zone_map_photo_url": zone_map_photo_url,
            "profile_photo_url": profile_photo_url,
            "face_object_position": _dict(protocol.get("images")).get("face_object_position") or WEB_MAP_OBJECT_POSITION,
        },
        "hero": {
            "title": "Персональный протокол лица",
            "title_accent": "протокол",
            "personal_conclusion": simplify_report_language(hero_conclusion, limit=520),
            "badges": [
                {"label": "Визуальный возраст", "value": _years_phrase(visual_age)},
                {"label": "Тип старения", "value": aging_name},
                {"label": "Главный фокус", "value": main_focus},
            ],
            "cta_text": cta_text,
            "cta_url": cta_url,
        },
        "story": {
            "current_appearance": {
                "title": "Сначала главное: что видно по фото",
                "text": simplify_report_language(current_text, limit=520),
                "cards": appearance_cards,
            },
            "main_focus": {
                "title": f"Что стоит поддержать в первую очередь — {main_focus}",
                "text": simplify_report_language(focus_text, limit=440),
                "zones": priority_zones[:4] or [main_focus],
            },
            "potential": {
                "level": "Что изменится визуально",
                "text": (
                    "Твой результат — не другое лицо, а более свежая и отдохнувшая версия тебя. "
                    "Когда ключевые зоны выглядят легче, лицо воспринимается мягче, моложе и естественно ухоженнее."
                ),
                "items": potential_items,
                "cta_text": cta_text,
            },
        },
        "zone_map": {
            "source": zone_map_source,
            "image_url": zone_map_photo_url,
            "image_mode": zone_map_image_mode,
            "legend": {"good": "Все хорошо", "attention": "Зона внимания", "priority": "Приоритет"},
            "zones": canonical_zones,
        },
        "profile": profile_view,
        "benefits": {"title": "Что фейсфитнес даст именно тебе", "items": deduped_benefits},
        "early_changes": {
            "title": "Что ты можешь заметить первым",
            "intro": "Первые изменения обычно выглядят очень естественно: ты видишь в зеркале то же лицо, но более свежее, легкое и отдохнувшее.",
            "items": early_items,
        },
        "future": {
            "title": "Почему важно начать сейчас",
            "without_work": without_work,
            "with_work": with_work,
            "age_forecast": {
                "target_range": f"{max(20, client_age // 10 * 10)}–{max(30, client_age // 10 * 10 + 10)}",
                "label": "Твой понятный прогноз",
                "text": (
                    f"Сейчас хороший момент поддержать {zone_reading_object}. "
                    f"Пока изменения мягкие, курс может дать самый красивый эффект: {course_result}"
                ),
                "age_cards": _age_cards(client_age, aging_id),
            },
        },
        "details": {
            "items": _detail_items(
                visual_age=visual_age,
                passport_age=passport_age,
                skin_type_name=skin_type_name,
                skin_story_text=skin_story_text,
                strengths_text=strengths_text,
                feature_phrase=feature_phrase,
                zone_effects=zone_effects,
                course_result=course_result,
                aging_name=aging_name,
                aging_id=aging_id,
                mixed_components=mixed_components,
                zones=canonical_zones,
            )
        },
        "final_summary": {
            "text": simplify_report_language(final_summary_text or "", limit=420),
        },
        "final_cta": {
            "label": "Итог",
            "title": "Раскрыть красоту, <em>которая уже есть</em>",
            "text": _with_name(
                lead_name,
                "",
                (
                    f"сейчас важно поддержать {zone_reading_object}, чтобы лицо выглядело свежее, моложе и выразительнее. "
                    "Курс помогает сделать взгляд легче, контур собраннее и общее впечатление более отдохнувшим. "
                    "Именно для этого создан курс Bella Vladi FaceLifting."
                ),
            ),
            "button_text": cta_text,
            "url": cta_url,
            "note": "В программе ты получишь упражнения под твои зоны и понятную регулярность, которая помогает увидеть результат в зеркале.",
        },
        "footer": "Bella Vladi · Face Protocol · Это предварительный визуальный AI-разбор по фото. Не медицинское заключение и не замена консультации специалиста.",
        "meta": {"main_segment": canonical_zones[0]["key"] if canonical_zones else "", "lead_temperature": "warm"},
        "source_trace": {
            "version": WEB_REPORT_V6_VERSION,
            "content_sources": ["analysis_json", "protocol_copy_json", "face_protocol_zone_map", "aging_knowledge_base"],
            "aging_type": aging_id,
            "aging_type_name": aging_name,
            "mixed_components": mixed_components,
            "uses_photo_protocol_zone_map": bool(photo_zone_map),
            "uses_face_protocol_image": bool(face_protocol_url),
            "uses_zone_map_crop": bool(zone_map_crop_url),
            "uses_original_photo_zone_overlay": not bool(zone_map_crop_url) and bool(zone_map_photo_url),
            "zone_map_inserted_in_hero": False,
            "zone_map_inserted_in_story": False,
            "zone_map_inserted_in_map_block": True,
            "passport_age": passport_age,
            "visual_age": visual_age,
            "visual_age_rule": "passport_age_plus_2_or_3",
            "zone_warnings": zone_warnings,
        },
        "quality": {},
    }
    quality = validate_web_report_quality(view_model)
    if zone_warnings:
        quality["warnings"].extend(zone_warnings)
    view_model["quality"] = quality
    return view_model


buildBellaWebReportV6ViewModel = build_bella_web_report_v6_view_model
