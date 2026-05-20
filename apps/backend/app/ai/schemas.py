from typing import Literal

from pydantic import BaseModel, Field


class SkinVisualAge(BaseModel):
    estimated_range: str
    explanation: str
    confidence: Literal["low", "medium", "high"] = "medium"


class SkinType(BaseModel):
    type: str
    features: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    attention_points: list[str] = Field(default_factory=list)


class FaceTypeAndAgingType(BaseModel):
    face_type: str
    aging_type: str
    explanation: str


class Zone(BaseModel):
    number: int
    name: str
    status: Literal["good", "attention", "priority"]
    color: Literal["green", "yellow", "red"]
    short_comment: str
    reason: str
    recommended_focus: str


class TimeForecast(BaseModel):
    first_changes: str
    visible_changes: str
    stable_result: str


class FaceAnalysis(BaseModel):
    skin_visual_age: SkinVisualAge
    skin_type: SkinType
    face_type_and_aging_type: FaceTypeAndAgingType
    zones: list[Zone]
    causes: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    facefitness_benefits: list[str] = Field(default_factory=list)
    time_forecast: TimeForecast
    summary: str
    cta_recommendation: str


ANALYSIS_JSON_SCHEMA: dict = {
    "type": "object",
    "required": [
        "skin_visual_age",
        "skin_type",
        "face_type_and_aging_type",
        "zones",
        "causes",
        "strengths",
        "facefitness_benefits",
        "time_forecast",
        "summary",
        "cta_recommendation",
    ],
}

