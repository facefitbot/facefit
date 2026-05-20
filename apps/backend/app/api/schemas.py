from __future__ import annotations

from typing import Any

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LeadPatch(BaseModel):
    status: str | None = None
    tags: list[str] | None = None
    manager_comment: str | None = None
    source: str | None = None


class ReviewPatch(BaseModel):
    moderation_status: str | None = None
    report_json: dict[str, Any] | None = None
    status: str | None = None


class AfterPhotoApproveVariant(BaseModel):
    variant_path: str


class PromptPatch(BaseModel):
    content: str | None = None
    is_active: bool | None = None


class SettingsPatch(BaseModel):
    welcome_text: str | None = None
    consent_text: str | None = None
    photo_instruction_text: str | None = None
    waiting_text: str | None = None
    after_analysis_text: str | None = None
    disclaimer: str | None = None
    cta_text: str | None = None
    instagram_url: str | None = None
    whatsapp_url: str | None = None
    telegram_url: str | None = None
    after_photo_enabled: bool | None = None
    manual_moderation_enabled: bool | None = None
    regeneration_enabled: bool | None = None
    analysis_limit_per_user: int | None = None
    problem_catalog: list[dict[str, str]] | None = None
    ai_settings: dict[str, Any] | None = None


class BroadcastCreate(BaseModel):
    title: str
    message_type: str = "text"
    text: str | None = None
    media_path: str | None = None
    buttons: list[dict[str, str]] = Field(default_factory=list)
    audience_filter: dict[str, Any] = Field(default_factory=dict)


class CampaignCreate(BaseModel):
    slug: str
    title: str
    start_payload: str | None = None


class AdminCreate(BaseModel):
    email: EmailStr
    password: str
    role: str = "manager"


class AdminPatch(BaseModel):
    password: str | None = None
    role: str | None = None
    is_active: bool | None = None
