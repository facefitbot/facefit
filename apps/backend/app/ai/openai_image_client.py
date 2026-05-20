from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageOps

from app.core.config import settings


def _normalize_protocol_image(image_bytes: bytes, output_path: str) -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    image = ImageOps.exif_transpose(image)
    target_size = (1080, 1350)
    result = ImageOps.fit(image, target_size, method=Image.Resampling.LANCZOS)
    result.save(output_path, quality=96)
    return output_path


def build_openai_protocol_background_prompt(slide_kind: str) -> str:
    kind_titles = {
        "face_map": "minimal face map protocol slide",
        "summary": "minimal summary protocol slide",
        "plan": "minimal plan and forecast protocol slide",
    }
    return f"""
Create only a premium minimalist vertical background, 1080x1350, for a Russian Bella Vladi Face Protocol Telegram slide.

Slide purpose: {kind_titles.get(slide_kind, slide_kind)}

Style:
- ultra clean premium beauty editorial
- warm ivory / milk white base
- very subtle champagne paper texture
- barely visible dusty rose and sage undertones only near the edges
- lots of calm empty space
- no watercolor blobs, no marble veins, no decorative objects
- no text, no letters, no numbers, no logo, no watermark
- no cards, no UI, no frames, no people, no face
- no shadows except extremely soft ambient depth

The image will be used under exact code-rendered typography and UI layers, so keep the center calm, bright and uncluttered.
"""


def _extract_image_bytes(data: dict[str, Any]) -> bytes:
    item = (data.get("data") or [{}])[0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    if item.get("url"):
        response = httpx.get(item["url"], timeout=settings.ai_timeout_seconds)
        response.raise_for_status()
        return response.content
    raise RuntimeError("OpenAI image generation did not return image bytes")


def _post_generation(payload: dict[str, Any]) -> dict[str, Any]:
    raise RuntimeError("LEGACY_OPENAI_IMAGES_GENERATE_DISABLED_USE_AFTER_PHOTO_IMAGE_EDIT")


def generate_protocol_background_with_openai(output_path: str, slide_kind: str) -> str:
    model = settings.openai_protocol_image_model
    if not model:
        raise RuntimeError("OPENAI_PROTOCOL_IMAGE_MODEL is not configured")

    payload = {
        "model": model,
        "prompt": build_openai_protocol_background_prompt(slide_kind),
        "size": "1024x1536",
        "n": 1,
    }
    try:
        data = _post_generation({**payload, "quality": "high"})
    except RuntimeError as exc:
        if "quality" not in str(exc).lower():
            raise
        data = _post_generation(payload)
    return _normalize_protocol_image(_extract_image_bytes(data), output_path)
