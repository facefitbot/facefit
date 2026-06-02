from __future__ import annotations

import re
from typing import Any


STATUS_ORDER = {"good": 0, "attention": 1, "priority": 2}
STATUS_LABELS = {
    "good": "Всё хорошо",
    "attention": "Зона внимания",
    "priority": "Приоритет",
}
STATUS_COLORS = {
    "good": "green",
    "attention": "yellow",
    "priority": "red",
}

ZONE_ALIASES = {
    "область глаз / веки": "Зона глаз",
    "нависшее веко / мешки под глазами": "Зона глаз",
    "нависшее веко": "Зона глаз",
    "мешки под глазами": "Зона глаз",
    "потеря овала / брыли": "Овал лица",
    "брыли": "Овал лица",
    "второй подбородок": "Овал лица",
    "отёчность и усталый вид": "Отёчность",
    "отечность и усталый вид": "Отёчность",
    "носогубные складки": "Носогубная зона",
    "носогубка": "Носогубная зона",
    "межбровная морщина": "Межбровье",
    "межбровная зона": "Межбровье",
    "около-ротовая зона": "Околоротовая зона",
    "около ротовая зона": "Околоротовая зона",
    "около рта": "Околоротовая зона",
    "нижняя треть": "Овал лица",
    "подбородок": "Овал лица",
}

DEFAULT_ZONE_TITLES = [
    "Лоб и межбровье",
    "Зона глаз",
    "Средняя треть",
    "Носогубная зона",
    "Околоротовая зона",
    "Овал лица",
]

FITNESS_BENEFITS = [
    "уменьшить отёчность и сделать лицо визуально легче",
    "сделать взгляд более свежим и открытым",
    "поддержать более чёткий овал лица",
    "улучшить общий тонус без резких изменений",
    "дать лицу более отдохнувший вид",
    "помочь замедлить возрастные изменения при регулярной работе",
]

_RESULT_TEXT_RE = re.compile(
    r"\b("
    r"работа|работать|проработк|поможет|помогает|"
    r"упражнен|трениров|укреплен|поддерж|сохран|"
    r"раскрыть|уменьшить|вернуть|сделать|придавая"
    r")\w*",
    flags=re.IGNORECASE,
)


def clean_report_text(value: Any, fallback: str = "") -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"[*_`#>]+", "", text)
    text = re.sub(r"\bп\s*р\s*и\s*о\s*р\s*и\s*т\s*е\s*т\b", "Приоритет", text, flags=re.IGNORECASE)
    text = re.sub(r"\b[Пп]роблем(а|ы|у|ой|е|ами|ах)?\b", "зона внимания", text)
    text = re.sub(r"\b[Бб]рыли\b", "снижение чёткости овала", text)
    text = re.sub(r"\b[Мм]ешки под глазами\b", "отёчность в зоне глаз", text)
    text = re.sub(r"\bвыраженн\w+\s+пастоз\w*\b", "лёгкая припухлость", text, flags=re.IGNORECASE)
    text = re.sub(r"\b[Пп]астоз\w*\b", "лёгкая припухлость", text)
    text = re.sub(r"\b[Мм]икроциркуляц\w*\b", "питание тканей", text)
    text = re.sub(r"\b[Лл]имфодренаж\w*\b", "мягкая работа с отёчностью", text)
    text = re.sub(r"\b[Лл]имфоток\w*\b", "лёгкость тканей", text)
    text = re.sub(r"\b[Гг]ипертонус\w*\b", "мышечное напряжение", text)
    text = re.sub(r"\b[Нн]ормальная кожа\b", "кожа с ровной плотной базой", text)
    text = re.sub(r"\b[Нн]ормаль\w+\b", "комбинированная с ровной плотной базой", text)
    text = re.sub(r"\b[Оо]ваал\w*\b", lambda match: "Овала" if match.group(0)[0].isupper() else "овала", text)
    text = text.replace("normal", "комбинированная с ровной плотной базой")
    text = re.sub(r"\b[Лл]егк(?:ая|ой|ую|их|ими|ой)?\s+лёгк(?:ая|ой|ую|их|ими|ой)?\s+припухлость\b", "лёгкая припухлость", text)
    text = re.sub(r"\b[Лл]ёгк(?:ая|ой|ую|их|ими|ой)?\s+лёгк(?:ая|ой|ую|их|ими|ой)?\s+припухлость\b", "лёгкая припухлость", text)
    text = re.sub(r"\bуменьшить лёгкая припухлость\b", "уменьшить отёчность", text, flags=re.IGNORECASE)
    text = re.sub(r"\bуменьшения лёгкая припухлость\b", "уменьшения отёчности", text, flags=re.IGNORECASE)
    text = re.sub(r"\bс лёгкая припухлость\b", "с отёчностью", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+([.,:;])", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or fallback


def normalize_zone_title(value: Any, fallback: str = "Зона лица") -> str:
    text = clean_report_text(value, fallback).strip(" .,:;—–-")
    lowered = text.lower()
    if lowered in ZONE_ALIASES:
        return ZONE_ALIASES[lowered]
    for source, target in ZONE_ALIASES.items():
        if source in lowered:
            return target
    if re.search(r"лоб|межбров|бров", lowered):
        return "Лоб и межбровье" if "лоб" in lowered and "межбров" in lowered else text
    if re.search(r"глаз|век|нососл", lowered):
        return "Зона глаз"
    if re.search(r"щ[её]к|средн|скул", lowered):
        return "Средняя треть"
    if re.search(r"носогуб", lowered):
        return "Носогубная зона"
    if re.search(r"рот|губ|около.?рот", lowered):
        return "Околоротовая зона"
    if re.search(r"овал|нижн|подбород|челюст", lowered):
        return "Овал лица"
    return text[:1].upper() + text[1:] if text else fallback


def report_status(value: Any = None, color: Any = None) -> str:
    text = clean_report_text(value).lower()
    color_text = clean_report_text(color).lower()
    if text in {"good", "green", "всё хорошо", "все хорошо", "сильная зона"} or color_text in {"green", "зелёный", "зеленый"}:
        return "good"
    if text in {"priority", "red", "приоритет", "active", "active_focus", "активный фокус"} or color_text in {"red", "красный", "orange", "оранжевый"}:
        return "priority"
    return "attention"


def status_label(status: Any) -> str:
    return STATUS_LABELS[report_status(status)]


def status_color(status: Any) -> str:
    return STATUS_COLORS[report_status(status)]


def stronger_status(current: str, candidate: str) -> str:
    return candidate if STATUS_ORDER.get(candidate, 1) > STATUS_ORDER.get(current, 1) else current


def age_forecast_horizon(age: int | None) -> int:
    if not age or age < 20:
        return 40
    if 20 <= age <= 25:
        return 40
    if 30 <= age <= 39:
        return 55 if age >= 35 else 50
    if age >= 40:
        return 65 if age >= 45 else 60
    return min(50, age + 20)


def face_change_scenarios(focus: str = "зона глаз и овал", age: int | None = None) -> list[dict[str, str]]:
    horizon = age_forecast_horizon(age)
    focus_text = clean_report_text(focus, "зона глаз и овал").strip(" .")
    return [
        {
            "title": "Без регулярной работы",
            "text": (
                "Отёчность может становиться устойчивее, взгляд — тяжелее, "
                "а овал лица — мягче. Сильнее всего это обычно заметно в зонах: "
                f"{focus_text}."
            ),
        },
        {
            "title": "При регулярной работе",
            "text": (
                "Можно дольше сохранять свежесть, чёткость черт, тонус "
                "и более отдохнувший вид."
            ),
        },
        {
            "title": f"Ориентир до {horizon} лет",
            "text": (
                "Фейсфитнес не обещает остановить возраст, но при регулярной работе "
                "может помогать поддерживать лицо более лёгким, свежим и собранным."
            ),
        },
    ]


def face_change_scenarios_text(focus: str = "зона глаз и овал", age: int | None = None) -> str:
    return "\n\n".join(f"{item['title']}: {item['text']}" for item in face_change_scenarios(focus, age))


def fitness_benefits_text() -> str:
    return (
        "Фейсфитнес помогает лицу выглядеть свежее, легче и собраннее. "
        "При регулярной работе можно уменьшить отёчность, раскрыть взгляд, "
        "поддержать овал, улучшить общий тонус, получить более отдохнувший вид "
        "и мягко замедлять возрастные изменения."
    )


def zone_visible_text(title: Any, status: Any = "attention") -> str:
    zone = normalize_zone_title(title).lower()
    st = report_status(status)
    if st == "good":
        return "Зона выглядит спокойно и поддерживает гармонию лица."
    if "глаз" in zone:
        return "Зона глаз может добавлять усталость и делать взгляд тяжелее."
    if "лоб" in zone or "межбров" in zone:
        return "Есть напряжение, из-за которого взгляд может выглядеть строже."
    if "носогуб" in zone:
        return "Носогубная зона может делать лицо визуально более уставшим."
    if "сред" in zone:
        return "Средняя часть лица может выглядеть менее лёгкой и свежей."
    if "рот" in zone:
        return "Околоротовая зона может утяжелять выражение лица."
    if "овал" in zone:
        return "Овал может выглядеть мягче и менее чётким."
    if "отёч" in zone or "отеч" in zone:
        return "Есть лёгкая припухлость, из-за которой лицо может выглядеть менее чётким."
    return "В этой зоне есть мягкий визуальный фокус."


def zone_result_text(title: Any, status: Any = "attention") -> str:
    zone = normalize_zone_title(title).lower()
    if report_status(status) == "good":
        return "Работа поможет сохранить эту сильную сторону."
    if "глаз" in zone:
        return "Работа поможет сделать взгляд более открытым и свежим."
    if "лоб" in zone or "межбров" in zone:
        return "Работа поможет смягчить выражение и раскрыть взгляд."
    if "сред" in zone or "носогуб" in zone:
        return "Работа поможет лицу выглядеть более отдохнувшим."
    if "рот" in zone:
        return "Работа поможет сделать выражение мягче и легче."
    if "овал" in zone:
        return "Работа поможет поддержать более чёткий овал лица."
    if "отёч" in zone or "отеч" in zone:
        return "Работа поможет уменьшить отёчность и вернуть лицу лёгкость."
    return "Работа поможет лицу выглядеть свежее и собраннее."


def zone_recommendation(title: Any, status: Any = "attention") -> str:
    zone = normalize_zone_title(title).lower()
    if report_status(status) == "good":
        return "Сохранять мягкую регулярность без перегруза."
    if "глаз" in zone:
        return "Начать с шеи, мягкой работы с отёчностью и расслабления верхней части лица."
    if "лоб" in zone or "межбров" in zone:
        return "Начать с расслабления лба, межбровья и дыхания."
    if "овал" in zone:
        return "Подключать шею, осанку и мягкий тонус овала."
    return "Работать мягко и регулярно, без силового перегруза."


def looks_like_zone_result_text(value: Any) -> bool:
    text = clean_report_text(value).lower()
    if not text:
        return False
    return bool(_RESULT_TEXT_RE.search(text))


def normalize_zone_copy(
    title: Any,
    status: Any = "attention",
    *,
    visible: Any = None,
    result: Any = None,
    recommendation: Any = None,
) -> dict[str, str]:
    zone_title = normalize_zone_title(title)
    zone_status = report_status(status)
    visible_text = clean_report_text(visible)
    result_text = clean_report_text(result)
    recommendation_text = clean_report_text(recommendation)

    if not visible_text or looks_like_zone_result_text(visible_text):
        visible_text = zone_visible_text(zone_title, zone_status)
    if (
        not result_text
        or result_text.lower() == visible_text.lower()
        or not looks_like_zone_result_text(result_text)
    ):
        result_text = zone_result_text(zone_title, zone_status)
    if (
        not recommendation_text
        or recommendation_text.lower() in {visible_text.lower(), result_text.lower()}
    ):
        recommendation_text = zone_recommendation(zone_title, zone_status)

    return {
        "visible": visible_text,
        "result": result_text,
        "recommendation": recommendation_text,
    }
