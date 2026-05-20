from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["good", "attention", "priority"]


class SkinAgeCopy(BaseModel):
    value: str = "32"
    unit: str = "лет"
    comment: str = "Кожа выглядит молодой, есть лёгкая усталость."
    score: str = "78/100"


class SkinTypeCopy(BaseModel):
    title: str = "Комбинированная, склонная к отёчности"
    bullets: list[str] = Field(
        default_factory=lambda: [
            "Лёгкая жирность в T-зоне.",
            "Есть признаки обезвоженности.",
            "Плюс: хорошая плотность кожи.",
        ]
    )


class FaceAgingCopy(BaseModel):
    face_type: str = "Овальное лицо, мягкие черты"
    aging_type: str = "Усталый тип старения"
    bullets: list[str] = Field(
        default_factory=lambda: [
            "Акцент на глаза и нижнюю треть.",
            "Овал требует поддержки.",
            "Носогубная зона — зона внимания.",
        ]
    )
    forecast: list[str] = Field(
        default_factory=lambda: [
            "20–30 лет: возможны мимические линии в зоне лба и межбровья.",
            "30–40 лет: может снижаться тонус средней трети лица.",
            "40+ лет: овал и носогубная зона требуют регулярной поддержки.",
        ]
    )
    strong_base: str = "Сильная костная база и скулы — хороший антиэйдж-фактор."


class ZoneCopy(BaseModel):
    number: int
    label: str
    status: Status = "attention"


class GrowthZoneCopy(BaseModel):
    label: str
    status: Status = "attention"


class ProtocolCopy(BaseModel):
    skin_age: SkinAgeCopy = Field(default_factory=SkinAgeCopy)
    skin_type: SkinTypeCopy = Field(default_factory=SkinTypeCopy)
    face_aging: FaceAgingCopy = Field(default_factory=FaceAgingCopy)
    zones: list[ZoneCopy] = Field(default_factory=list)
    causes: list[str] = Field(
        default_factory=lambda: [
            "Лимфоток в зоне глаз требует активации.",
            "Напряжение межбровки усиливает складку.",
            "Осанка влияет на овал лица.",
        ]
    )
    why_intro: str = "Исходя из вашего типа кожи и лица, главный фактор — баланс мышц, лимфы и осанки."
    why_outro: str = "Со временем мышцы теряют тонус, а зоны зажимов становятся заметнее. Этот процесс можно мягко замедлить."
    strengths: list[str] = Field(
        default_factory=lambda: [
            "Выразительные глаза.",
            "Хорошая плотность кожи.",
            "Есть потенциал четкого овала.",
        ]
    )
    benefits: list[str] = Field(
        default_factory=lambda: [
            "Снизит утреннюю отёчность.",
            "Смягчит носогубную зону.",
            "Поможет собрать нижний контур.",
        ]
    )
    benefits_outro: str = "Собранный овал, свежий взгляд и длинная шея дадут лицу естественный лифтинг-эффект."
    forecast: list[str] = Field(
        default_factory=lambda: [
            "2 недели — свежее лицо.",
            "1 месяц — открытый взгляд.",
            "3 месяца — устойчивее овал.",
        ]
    )
    growth_zones: list[GrowthZoneCopy] = Field(default_factory=list)
    final_summary: str = "Главный фокус — вернуть четкость овалу, снизить отёчность и расслабить межбровье."


DEFAULT_ZONES: list[dict] = [
    {"number": 1, "label": "Лоб", "status": "attention"},
    {"number": 2, "label": "Межбровье", "status": "priority"},
    {"number": 3, "label": "Зона глаз", "status": "priority"},
    {"number": 4, "label": "Носогубная зона", "status": "attention"},
    {"number": 5, "label": "Околоротовая", "status": "good"},
    {"number": 6, "label": "Овал лица", "status": "priority"},
]

DEFAULT_GROWTH_ZONES: list[dict] = [
    {"label": "Нависшее веко", "status": "priority"},
    {"label": "Шея", "status": "attention"},
    {"label": "Овал лица", "status": "priority"},
    {"label": "Зона глаз", "status": "attention"},
    {"label": "Качество кожи", "status": "good"},
]

EXAMPLE_PROTOCOL_COPY: dict = {
    "skin_age": {
        "value": "32",
        "unit": "лет",
        "comment": "Кожа выглядит молодой, есть лёгкая усталость.",
        "score": "78/100",
    },
    "skin_type": {
        "title": "Комбинированная, склонная к отёчности",
        "bullets": [
            "Лёгкая жирность в T-зоне.",
            "Есть признаки обезвоженности.",
            "Плюс: хорошая плотность кожи.",
        ],
    },
    "face_aging": {
        "face_type": "Овальное лицо, мягкие черты",
        "aging_type": "Усталый тип старения",
        "bullets": [
            "Акцент на глаза и нижнюю треть.",
            "Овал требует поддержки.",
            "Носогубная зона — зона внимания.",
        ],
        "forecast": [
            "20–30 лет: возможны мимические линии в зоне лба и межбровья.",
            "30–40 лет: может снижаться тонус средней трети лица.",
            "40+ лет: овал и носогубная зона требуют регулярной поддержки.",
        ],
        "strong_base": "Сильная костная база и скулы — хороший антиэйдж-фактор.",
    },
    "zones": DEFAULT_ZONES,
    "causes": [
        "Лимфоток в зоне глаз требует активации.",
        "Напряжение межбровки усиливает складку.",
        "Осанка влияет на овал лица.",
    ],
    "why_intro": "Исходя из вашего типа кожи и лица, главный фактор — баланс мышц, лимфы и осанки.",
    "why_outro": "Со временем мышцы теряют тонус, а зоны зажимов становятся заметнее. Этот процесс можно мягко замедлить.",
    "strengths": [
        "Выразительные глаза.",
        "Хорошая плотность кожи.",
        "Есть потенциал четкого овала.",
    ],
    "benefits": [
        "Снизит утреннюю отёчность.",
        "Смягчит носогубную зону.",
        "Поможет собрать нижний контур.",
    ],
    "benefits_outro": "Собранный овал, свежий взгляд и длинная шея дадут лицу естественный лифтинг-эффект.",
    "forecast": [
        "2 недели — свежее лицо.",
        "1 месяц — открытый взгляд.",
        "3 месяца — устойчивее овал.",
    ],
    "growth_zones": DEFAULT_GROWTH_ZONES,
    "final_summary": "Главный фокус — вернуть четкость овалу, снизить отёчность и расслабить межбровье.",
}
