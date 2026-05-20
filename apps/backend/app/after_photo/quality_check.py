from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat

from app.ai.json_repair import parse_json_safely
from app.after_photo.schemas import AfterPhotoQualityResult
from app.core.config import settings

logger = logging.getLogger(__name__)


QUALITY_SYSTEM_PROMPT = """You evaluate AI-generated after-photo variants for a beauty face-fitness product.
Return strict JSON only. Do not praise the image. Be conservative.
The best result must preserve the same person's identity, age category, ethnicity, facial proportions, camera angle, expression and natural skin texture.
Reject or request retry if the result looks like plastic surgery, fillers, a beauty filter, doll skin, heavy retouching, or a different person."""

QUALITY_USER_PROMPT = """Compare the original image with the candidate after-photo.
Score only this candidate using this schema:
{
  "same_identity": true,
  "identity_score": 0.0,
  "realism_score": 0.0,
  "visible_improvement": true,
  "skin_texture_preserved": true,
  "too_much_retouch": false,
  "plastic_surgery_effect": false,
  "recommendation": "approve|retry|manual_review|reject",
  "reason": "short reason"
}
Approve only if identity_score >= 0.82, realism_score >= 0.75, visible_improvement is true, too_much_retouch is false, and plastic_surgery_effect is false."""


def _image_to_data_url(path: str) -> str:
    file_path = Path(path)
    mime = "image/png" if file_path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(file_path.read_bytes()).decode('ascii')}"


def _mean_image_difference(original_path: str, variant_path: str) -> float:
    original = Image.open(original_path).convert("RGB").resize((160, 160), Image.Resampling.LANCZOS)
    variant = Image.open(variant_path).convert("RGB").resize((160, 160), Image.Resampling.LANCZOS)
    diff = ImageChops.difference(original, variant).convert("L")
    return float(ImageStat.Stat(diff).mean[0])


def _fallback_quality_result(original_photo_path: str, variant_path: str, reason: str) -> AfterPhotoQualityResult:
    try:
        diff = _mean_image_difference(original_photo_path, variant_path)
        visible = 1.5 <= diff <= 38.0
        realism = 0.66 if visible else 0.58
        identity = 0.74 if diff <= 38.0 else 0.55
        text = f"{reason}; fallback image diff={diff:.2f}. Needs manual review."
    except Exception as exc:
        visible = False
        realism = 0.0
        identity = 0.0
        text = f"{reason}; fallback scoring failed: {exc}"
    return AfterPhotoQualityResult(
        variant_path=variant_path,
        same_identity=identity >= 0.7,
        identity_score=identity,
        realism_score=realism,
        visible_improvement=visible,
        skin_texture_preserved=False,
        too_much_retouch=False,
        plastic_surgery_effect=False,
        recommendation="manual_review",
        reason=text,
        fallback_scoring=True,
    )


def _vision_quality_result(original_photo_path: str, variant_path: str) -> AfterPhotoQualityResult:
    if not (settings.openai_api_key and settings.openai_vision_qa_model):
        return _fallback_quality_result(original_photo_path, variant_path, "OpenAI vision QA unavailable")

    try:
        from openai import BadRequestError, OpenAI
    except Exception as exc:
        return _fallback_quality_result(original_photo_path, variant_path, f"OpenAI client unavailable: {exc}")

    client = OpenAI(api_key=settings.openai_api_key)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": QUALITY_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": QUALITY_USER_PROMPT},
                {"type": "text", "text": "Original photo:"},
                {"type": "image_url", "image_url": {"url": _image_to_data_url(original_photo_path)}},
                {"type": "text", "text": "Candidate after-photo:"},
                {"type": "image_url", "image_url": {"url": _image_to_data_url(variant_path)}},
            ],
        },
    ]
    kwargs: dict[str, Any] = {
        "model": settings.openai_vision_qa_model,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "max_tokens": 500,
    }
    response = None
    for _ in range(3):
        try:
            response = client.chat.completions.create(**kwargs)
            break
        except BadRequestError as exc:
            message = str(exc).lower()
            if "max_tokens" in message and "max_completion_tokens" in message and "max_tokens" in kwargs:
                kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
                continue
            if "temperature" in message and "temperature" in kwargs:
                kwargs.pop("temperature", None)
                continue
            raise
    if response is None:
        raise RuntimeError("Vision QA returned no response")
    content = response.choices[0].message.content or "{}"
    data = parse_json_safely(content)
    data["variant_path"] = variant_path
    try:
        return AfterPhotoQualityResult.model_validate(data)
    except Exception as exc:
        logger.warning("Vision QA returned invalid after-photo schema", exc_info=True)
        return _fallback_quality_result(original_photo_path, variant_path, f"Vision QA schema invalid: {exc}")


def run_after_photo_quality_check(original_photo_path: str, variant_paths: list[str]) -> dict:
    logger.info("Running after-photo quality check")
    results: list[AfterPhotoQualityResult] = []
    for path in variant_paths:
        try:
            results.append(_vision_quality_result(original_photo_path, path))
        except Exception as exc:
            logger.warning("After-photo quality check failed for %s", path, exc_info=True)
            results.append(_fallback_quality_result(original_photo_path, path, f"Vision QA failed: {exc}"))
    return {
        "results": [item.model_dump() for item in results],
        "used_vision_qa": bool(settings.openai_api_key and settings.openai_vision_qa_model),
    }
