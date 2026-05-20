from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from openai import BadRequestError, OpenAI
from pydantic import ValidationError

from app.ai.gemini_client import repair_or_structure_with_gemini
from app.ai.json_repair import parse_json_safely
from app.ai.prompts import (
    PERSONAL_INSIGHT_SYSTEM_PROMPT,
    PERSONAL_INSIGHT_USER_PROMPT,
    PROTOCOL_COPY_SYSTEM_PROMPT,
    PROTOCOL_COPY_USER_PROMPT,
    PROTOCOL_SLIDE_COPY_SYSTEM_PROMPT,
    PROTOCOL_SLIDE_COPY_USER_PROMPT,
    REPORT_PROMPT,
    build_analysis_system_prompt,
    build_analysis_user_prompt,
)
from app.ai.schemas import FaceAnalysis
from app.core.config import settings
from app.reports.face_protocol_final.normalize import build_protocol_copy_from_analysis, normalize_protocol_copy
from app.reports.face_protocol_final.schema import EXAMPLE_PROTOCOL_COPY
from app.reports.protocol_v4.schema import build_protocol_slide_copy_from_analysis, normalize_protocol_slide_copy


def _chat_completion_with_temperature_fallback(client: OpenAI, **kwargs: Any):
    try:
        return client.chat.completions.create(**kwargs)
    except BadRequestError as exc:
        message = str(exc)
        if "temperature" in kwargs and "temperature" in message and "unsupported" in message.lower():
            retry_kwargs = dict(kwargs)
            retry_kwargs.pop("temperature", None)
            return client.chat.completions.create(**retry_kwargs)
        raise


def _image_to_data_url(path: str) -> str:
    file_path = Path(path)
    mime = "image/png" if file_path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(file_path.read_bytes()).decode('ascii')}"


def _compose_stage_system_prompt(base_system_prompt: str | None, stage_prompt: str) -> str:
    base = (base_system_prompt or "").strip()
    stage = stage_prompt.strip()
    if not base:
        return stage
    return (
        f"{base}\n\n"
        "## ИНСТРУКЦИЯ ТЕКУЩЕГО ЭТАПА\n"
        f"{stage}\n\n"
        "Если базовый системный промпт описывает подробную схему анализа, используй ее как методический контекст. "
        "Формат ответа и обязательные поля для текущего запроса определяются инструкцией текущего этапа."
    )


def mock_analysis(selected_problems: list[str] | None = None) -> dict[str, Any]:
    selected = selected_problems or []
    priority_keywords = " ".join(selected).lower()

    def status_for(name: str) -> tuple[str, str]:
        key = name.lower()
        if any(word in priority_keywords for word in ["носогуб", "овал", "подбород", "брыли"]) and any(
            word in key for word in ["носогуб", "овал", "подбород"]
        ):
            return "priority", "red"
        if any(word in priority_keywords for word in ["веко", "глаз", "отеч", "устал"]) and any(
            word in key for word in ["глаз", "отеч"]
        ):
            return "attention", "yellow"
        if any(word in priority_keywords for word in ["межбров"]) and "межбров" in key:
            return "attention", "yellow"
        if name in {"Скулы", "Лоб"}:
            return "good", "green"
        return "attention", "yellow"

    zone_names = [
        "Лоб",
        "Межбровная зона",
        "Область глаз / веки",
        "Носогубная зона",
        "Скулы",
        "Овал лица",
        "Подбородок",
        "Шея",
        "Зона отечности",
    ]
    zones = []
    for index, name in enumerate(zone_names, start=1):
        status, color = status_for(name)
        zones.append(
            {
                "number": index,
                "name": name,
                "status": status,
                "color": color,
                "short_comment": "ресурсная зона" if status == "good" else "мягкая зона внимания",
                "reason": "Визуально зона может реагировать на тонус мышц, лимфоток, осанку и мимические привычки.",
                "recommended_focus": "мягкий лимфодренаж, расслабление зажимов и регулярные упражнения без перенапряжения.",
            }
        )

    return {
        "skin_visual_age": {
            "estimated_range": "примерно в диапазоне 32-38",
            "explanation": "Визуально кожа воспринимается свежей, с небольшим запасом для раскрытия тонуса и сияния.",
            "confidence": "medium",
        },
        "skin_type": {
            "type": "комбинированная, склонная к отечности",
            "features": ["Т-зона может быть активнее", "Щеки выглядят более спокойными", "Есть потенциал к свежести после лимфодренажа"],
            "strengths": ["Плотность кожи", "Хороший отклик на регулярный уход"],
            "attention_points": ["Отечность по утрам", "Тонус нижней трети", "Микроциркуляция"],
        },
        "face_type_and_aging_type": {
            "face_type": "ближе к овальному",
            "aging_type": "комбинированный с усталым компонентом",
            "explanation": "Главный акцент — мягко снять напряжение и отечность, поддержать овал и открыть взгляд.",
        },
        "zones": zones,
        "causes": ["гипертонус мимических мышц", "лимфозастой и отечность", "осанка и напряжение шеи", "стресс и недостаток сна"],
        "strengths": ["Выразительные глаза", "Хороший потенциал овала", "Естественная мягкость черт", "Хороший отклик на регулярные упражнения"],
        "facefitness_benefits": [
            "более свежий и отдохнувший вид",
            "снижение отечности",
            "мягкое улучшение овала лица",
            "расслабление межбровной зоны",
        ],
        "time_forecast": {
            "first_changes": "7-14 дней: больше свежести и меньше утренней отечности.",
            "visible_changes": "4-6 недель: заметнее тонус, взгляд и линия овала.",
            "stable_result": "8-12 недель: более устойчивый визуальный эффект при регулярной практике.",
        },
        "summary": "Главный фокус — лимфодренаж, расслабление зажимов и поддержка нижней трети лица.",
        "cta_recommendation": "Лучший следующий шаг — персональная программа Bella Vladi с мягкой регулярной нагрузкой.",
    }


def analyze_face(
    photo_path: str,
    user_name: str | None,
    selected_problems: list[str],
    knowledge_context: str,
    system_prompt: str,
) -> dict[str, Any]:
    if settings.ai_mock_mode:
        return mock_analysis(selected_problems)

    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.ai_timeout_seconds)
    response = _chat_completion_with_temperature_fallback(
        client,
        model=settings.openai_analysis_model,
        temperature=0.35,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": build_analysis_system_prompt(system_prompt)},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": build_analysis_user_prompt(user_name, selected_problems, knowledge_context)},
                    {"type": "image_url", "image_url": {"url": _image_to_data_url(photo_path)}},
                ],
            },
        ],
    )
    raw = response.choices[0].message.content or "{}"
    parsed = parse_json_safely(raw)
    try:
        return FaceAnalysis.model_validate(parsed).model_dump()
    except ValidationError:
        repaired = repair_or_structure_with_gemini(raw)
        if repaired:
            return FaceAnalysis.model_validate(repaired).model_dump()
        raise


def build_personal_insights_from_analysis(analysis_json: dict[str, Any], selected_problems: list[str] | None = None) -> dict[str, Any]:
    analysis = analysis_json if isinstance(analysis_json, dict) else {}
    selected = selected_problems or []
    aging = analysis.get("face_type_and_aging_type") if isinstance(analysis.get("face_type_and_aging_type"), dict) else {}
    zones = [zone for zone in analysis.get("zones", []) if isinstance(zone, dict)] if isinstance(analysis.get("zones"), list) else []
    priority = [zone for zone in zones if zone.get("status") in {"priority", "attention"} or zone.get("color") in {"red", "yellow"}]
    strengths = analysis.get("strengths") if isinstance(analysis.get("strengths"), list) else []

    def zone_name(zone: dict[str, Any], fallback: str) -> str:
        return str(zone.get("name") or zone.get("label") or fallback)

    why_items = []
    for zone in (priority or zones)[:4]:
        name = zone_name(zone, "Зона")
        short_comment = str(zone.get("short_comment") or "видна мягкая зона внимания")
        reason = str(zone.get("reason") or "на состояние зоны могут влиять лимфоток, тонус мышц и осанка")
        why_items.append(
            {
                "zone": name,
                "visible_sign": short_comment,
                "mechanism": reason,
                "personal_meaning": f"{name} влияет на то, насколько лицо выглядит свежим и собранным.",
                "short_protocol_bullet": f"{name}: {short_comment}; чаще связано с тонусом, лимфой и осанкой.",
            }
        )

    while len(why_items) < 3:
        why_items.append(
            {
                "zone": "Общее впечатление",
                "visible_sign": "лицу нужен более собранный и свежий визуальный ритм",
                "mechanism": "обычно это связано с лимфотоком, тонусом мышц и ежедневной мимикой",
                "personal_meaning": "именно это может забирать ощущение легкости лица.",
                "short_protocol_bullet": "Свежесть лица зависит от связки: лимфа, тонус мышц и положение шеи.",
            }
        )

    strength_items = []
    for item in strengths[:3]:
        text = str(item)
        strength_items.append(
            {
                "trait": text,
                "why_it_matters": "это ресурс, на который можно опереться в протоколе.",
                "short_protocol_bullet": text,
            }
        )
    while len(strength_items) < 3:
        fallback = ["Естественная выразительность лица", "Потенциал более четкого овала", "Хороший отклик на мягкий лимфодренаж"][len(strength_items)]
        strength_items.append(
            {
                "trait": fallback,
                "why_it_matters": "это база, которая помогает получить естественный визуальный результат.",
                "short_protocol_bullet": fallback,
            }
        )

    aging_type = str(aging.get("aging_type") or "комбинированный")
    main_zone = zone_name(priority[0], "зоны глаз и овала") if priority else "зоны глаз и овала"
    aging_lower = aging_type.lower()
    if "деформа" in aging_lower or "птоз" in aging_lower or "отеч" in aging_lower or "отёч" in aging_lower:
        strategy = [
            "Лимфодренаж снимет пастозность и сделает взгляд свежее.",
            "Работа с шеей поможет лицу легче отдавать жидкость.",
            "Тонус нижней трети сделает овал собраннее.",
            "Скулы и линия челюсти будут читаться чётче.",
        ]
    elif "муск" in aging_lower:
        strategy = [
            "Расслабление жевательных смягчит нижнюю треть.",
            "Снятие зажимов лба и межбровья откроет выражение лица.",
            "Баланс мимики уменьшит ощущение напряжённости.",
            "Мягкий тонус вернет чертам спокойствие и свежесть.",
        ]
    elif "мелк" in aging_lower or "морщ" in aging_lower:
        strategy = [
            "Мягкая стимуляция улучшит питание кожи изнутри.",
            "Деликатный массаж поможет коже выглядеть более живой.",
            "Работа без перенапряжения сохранит чёткий овал.",
            "Лицо будет выглядеть свежее и наполненнее.",
        ]
    elif "устал" in aging_lower:
        strategy = [
            "Микроциркуляция сделает лицо менее уставшим.",
            "Лимфодренаж откроет взгляд и снимет тени.",
            "Тонус средней трети смягчит носогубную зону.",
            "Лицо будет выглядеть отдохнувшим и собранным.",
        ]
    else:
        strategy = [
            "Лимфодренаж даст лицу больше свежести и лёгкости.",
            "Работа с шеей поддержит овал и нижнюю треть.",
            "Мягкий тонус сделает черты более собранными.",
            "Свежий взгляд и чётче овал дадут естественный лифтинг-эффект.",
        ]
    return {
        "main_hook": f"Главный фокус — понять, что именно забирает свежесть у {main_zone}.",
        "main_visual_conflict": f"Лицо имеет ресурс, но {main_zone} может забирать ощущение легкости и собранности.",
        "main_leverage_point": f"Самый заметный эффект даст работа с {main_zone}: лимфоток, тонус и расслабление зажимов.",
        "morphotype_story": {
            "type": aging_type,
            "why_this_type": str(aging.get("explanation") or "видны признаки смешанного влияния тонуса, лимфотока и мимики."),
            "what_is_happening": "Визуальное впечатление формируется связкой: мышцы, лимфа, осанка и качество кожи.",
            "how_it_may_change": "Без поддержки зона внимания может сильнее влиять на свежесть и четкость лица.",
            "strategy": "Сначала лимфодренаж и шея, затем расслабление зажимов и мягкое укрепление овала.",
        },
        "why_this_happens": why_items[:4],
        "strengths_explained": strength_items[:3],
        "facefitness_strategy": strategy,
        "avoid": ["Не перегружать зоны гипертонуса", "Не ждать эффекта только от ухода без работы с лимфой и шеей"],
        "final_personal_summary": str(analysis.get("summary") or f"Главный рычаг — {main_zone}: сделать лицо легче, свежее и собраннее."),
    }


def generate_personal_insights(
    analysis_json: dict[str, Any],
    selected_problems: list[str],
    knowledge_context: str = "",
    system_prompt: str | None = None,
) -> dict[str, Any]:
    model = settings.openai_protocol_copy_model or settings.openai_report_model or settings.openai_analysis_model
    fallback = build_personal_insights_from_analysis(analysis_json, selected_problems)
    if settings.ai_mock_mode or not (settings.openai_api_key and model):
        return fallback

    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.ai_timeout_seconds)
    response = _chat_completion_with_temperature_fallback(
        client,
        model=model,
        temperature=0.42,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _compose_stage_system_prompt(system_prompt, PERSONAL_INSIGHT_SYSTEM_PROMPT)},
            {
                "role": "user",
                "content": (
                    f"{PERSONAL_INSIGHT_USER_PROMPT}\n\n"
                    + json.dumps(
                        {
                            "analysis_json": analysis_json,
                            "selected_problems": selected_problems,
                            "knowledge_context": knowledge_context[:7000],
                        },
                        ensure_ascii=False,
                    )
                ),
            },
        ],
    )
    try:
        parsed = parse_json_safely(response.choices[0].message.content or "{}")
        return parsed if isinstance(parsed, dict) else fallback
    except Exception:
        return fallback


def generate_report_copy(
    analysis_json: dict[str, Any],
    selected_problems: list[str],
    knowledge_context: str,
    system_prompt: str | None = None,
    report_prompt: str | None = None,
    personal_insight_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if settings.ai_mock_mode or not (settings.openai_api_key and settings.openai_report_model):
        return {
            "editor_note": "Mock mode: отчет собран локально на основе структурированного анализа.",
            "selected_problems": selected_problems,
        }
    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.ai_timeout_seconds)
    stage_report_prompt = (report_prompt or REPORT_PROMPT).strip()
    response = _chat_completion_with_temperature_fallback(
        client,
        model=settings.openai_report_model,
        temperature=0.45,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": _compose_stage_system_prompt(
                    system_prompt,
                    f"{stage_report_prompt}\nОтвет строго JSON. Не добавляй markdown и пояснения вокруг JSON.",
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "analysis_json": analysis_json,
                        "personal_insight_json": personal_insight_json or {},
                        "selected_problems": selected_problems,
                        "knowledge_context": knowledge_context[:5000],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    )
    return parse_json_safely(response.choices[0].message.content or "{}")


def generate_protocol_slide_copy(analysis_json: dict[str, Any], selected_problems: list[str]) -> dict[str, Any]:
    model = settings.openai_protocol_copy_model or settings.openai_report_model or settings.openai_analysis_model
    fallback = build_protocol_slide_copy_from_analysis(analysis_json, selected_problems)
    if settings.ai_mock_mode or not (settings.openai_api_key and model):
        return fallback

    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.ai_timeout_seconds)
    response = _chat_completion_with_temperature_fallback(
        client,
        model=model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": PROTOCOL_SLIDE_COPY_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    f"{PROTOCOL_SLIDE_COPY_USER_PROMPT}\n\n"
                    + json.dumps(
                        {
                            "schema": {
                                "face_map": {
                                    "title": "AI Face Scan",
                                    "subtitle": "визуальный AI-разбор",
                                    "main_focus": ["Глаза", "Носогубка", "Овал"],
                                    "zones": [
                                        {"number": 1, "label": "Лоб", "status": "good", "shape": "forehead"},
                                        {"number": 2, "label": "Межбровка", "status": "attention", "shape": "glabella"},
                                        {"number": 3, "label": "Глаза", "status": "priority", "shape": "eyes"},
                                        {"number": 4, "label": "Носогубка", "status": "attention", "shape": "nasolabial"},
                                        {"number": 5, "label": "Скулы", "status": "good", "shape": "cheeks"},
                                        {"number": 6, "label": "Овал", "status": "priority", "shape": "jawline"},
                                        {"number": 7, "label": "Подбородок", "status": "attention", "shape": "chin"},
                                        {"number": 8, "label": "Шея", "status": "attention", "shape": "neck"},
                                    ],
                                },
                                "summary": {
                                    "skin_age": "до 95 символов",
                                    "skin_type": "до 95 символов",
                                    "aging_type": "до 95 символов",
                                    "strengths": "до 95 символов",
                                },
                                "plan": {
                                    "causes": ["до 55 символов"],
                                    "benefits": ["до 24 символов"],
                                    "forecast": ["до 38 символов"],
                                },
                            },
                            "limits": {
                                "zone_label": 14,
                                "main_focus_item": 18,
                                "summary_card_text": 78,
                                "main_conclusion": 92,
                                "causes_bullet": 55,
                                "benefits_chip": 24,
                                "forecast_item": 38,
                            },
                            "analysis_json": analysis_json,
                            "selected_problems": selected_problems,
                        },
                        ensure_ascii=False,
                    )
                ),
            },
        ],
    )
    parsed = parse_json_safely(response.choices[0].message.content or "{}")
    return normalize_protocol_slide_copy(parsed)


def generate_protocol_copy(
    analysis_json: dict[str, Any],
    selected_problems: list[str],
    knowledge_context: str = "",
    system_prompt: str | None = None,
    personal_insight_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    model = settings.openai_protocol_copy_model or settings.openai_report_model or settings.openai_analysis_model
    fallback = build_protocol_copy_from_analysis(analysis_json, selected_problems, personal_insight_json)
    if settings.ai_mock_mode or not (settings.openai_api_key and model):
        return fallback

    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.ai_timeout_seconds)
    response = _chat_completion_with_temperature_fallback(
        client,
        model=model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _compose_stage_system_prompt(system_prompt, PROTOCOL_COPY_SYSTEM_PROMPT)},
            {
                "role": "user",
                "content": (
                    f"{PROTOCOL_COPY_USER_PROMPT}\n\n"
                    + json.dumps(
                        {
                            "schema": EXAMPLE_PROTOCOL_COPY,
                            "limits": {
                                "skin_age.comment": 110,
                                "skin_type.title": 42,
                                "skin_type.bullet": 75,
                                "face_aging.face_type": 62,
                                "face_aging.aging_type": 78,
                                "face_aging.forecast": 3,
                                "face_aging.forecast_item": 82,
                                "face_aging.strong_base": 110,
                                "aging.bullet": 95,
                                "why_intro": 180,
                                "causes": 4,
                                "cause.bullet": 95,
                                "why_outro": 170,
                                "strengths": 3,
                                "strength.bullet": 75,
                                "benefits": 3,
                                "benefit.bullet": 75,
                                "benefits_outro": 130,
                                "forecast": 3,
                                "forecast.bullet": 75,
                                "growth_zones": 5,
                                "growth_zone.label": 22,
                                "final_summary": 170,
                                "zone.label": 22,
                            },
                            "analysis_json": analysis_json,
                            "personal_insight_json": personal_insight_json or {},
                            "selected_problems": selected_problems,
                            "knowledge_context": knowledge_context[:5000],
                        },
                        ensure_ascii=False,
                    )
                ),
            },
        ],
    )
    parsed = parse_json_safely(response.choices[0].message.content or "{}")
    return normalize_protocol_copy(parsed)
