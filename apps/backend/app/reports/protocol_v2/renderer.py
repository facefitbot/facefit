from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.reports.protocol_v2.slides import render_slide_1, render_slide_2, render_slide_3

logger = logging.getLogger(__name__)
LEGACY_RENDERER_ERROR = "LEGACY_FACE_PROTOCOL_RENDERER_DISABLED_USE_FINAL_V1"


def _background_for_slide(output_dir: Path, slide_kind: str, *, use_gemini: bool, allow_mock_background: bool) -> str | None:
    if not use_gemini:
        return None

    provider = settings.protocol_image_provider.lower()
    if provider not in {"openai", "gemini"} and not allow_mock_background:
        raise RuntimeError("Protocol v2 requires PROTOCOL_IMAGE_PROVIDER=openai or gemini for production rendering")

    try:
        if provider == "openai":
            from app.ai.openai_image_client import generate_protocol_background_with_openai

            output_path = output_dir / f"{slide_kind}_openai_background.jpg"
            return generate_protocol_background_with_openai(str(output_path), slide_kind)
        if provider == "gemini":
            from app.ai.gemini_client import generate_protocol_background_with_gemini

            output_path = output_dir / f"{slide_kind}_gemini_background.jpg"
            return generate_protocol_background_with_gemini(str(output_path), slide_kind)
        return None
    except Exception:
        if allow_mock_background:
            logger.warning("Protocol background failed for %s; using local preview background", slide_kind, exc_info=True)
            return None
        raise


def generate_slides(
    original_photo_path: str,
    output_dir: str,
    user_name: str,
    analysis_json: dict[str, Any],
    *,
    single_image: bool = False,
    use_gemini: bool = True,
    allow_mock_background: bool = False,
    extension: str = "jpg",
) -> list[str]:
    raise RuntimeError(LEGACY_RENDERER_ERROR)
    """Generate Bella Vladi Face Protocol v2 Telegram slides.

    This function is the only active protocol image renderer used by the worker.
    The old `protocol_image.py` template remains as legacy code only.
    """
    logger.warning("PROTOCOL_V2_RENDERER_ACTIVE")
    logger.info("USING_PROTOCOL_RENDERER=protocol_v2")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    ext = extension.lstrip(".").lower() or "jpg"

    specs = [
        ("face_map", f"slide_1_face_map.{ext}", render_slide_1),
        ("summary", f"slide_2_summary.{ext}", render_slide_2),
        ("plan", f"slide_3_plan_forecast.{ext}", render_slide_3),
    ]
    if single_image:
        specs = specs[:1]

    slide_paths: list[str] = []
    for slide_kind, file_name, renderer in specs:
        background = _background_for_slide(output, slide_kind, use_gemini=use_gemini, allow_mock_background=allow_mock_background)
        out_path = output / file_name
        if slide_kind == "face_map":
            slide_paths.append(
                renderer(
                    photo_path=original_photo_path,
                    output_path=out_path,
                    user_name=user_name,
                    analysis_json=analysis_json,
                    background_path=background,
                )
            )
        else:
            slide_paths.append(
                renderer(
                    output_path=out_path,
                    user_name=user_name,
                    analysis_json=analysis_json,
                    background_path=background,
                )
            )
    return slide_paths


def _protocol_date(value: datetime | str | None) -> str:
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, str) and value.strip():
        return value[:10]
    return datetime.now().strftime("%d.%m.%Y")


def generate_face_protocol_slides_v2(
    analysis_request_id: str,
    user_photo_path: str,
    analysis_json: dict[str, Any],
    user_name: str,
    created_at: datetime,
    output_dir: str,
    *,
    single_image: bool = False,
    use_ai_background: bool = True,
    allow_mock_background: bool = False,
) -> list[str]:
    raise RuntimeError(LEGACY_RENDERER_ERROR)
    logger.warning("PROTOCOL_V2_RENDERER_ACTIVE")
    logger.info("USING_PROTOCOL_RENDERER=protocol_v2")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    date_text = _protocol_date(created_at)
    specs = [
        ("face_map", f"protocol_v2_{analysis_request_id}_slide_1.png", render_slide_1),
        ("summary", f"protocol_v2_{analysis_request_id}_slide_2.png", render_slide_2),
        ("plan", f"protocol_v2_{analysis_request_id}_slide_3.png", render_slide_3),
    ]
    if single_image:
        specs = specs[:1]

    slides: list[str] = []
    for slide_kind, file_name, renderer in specs:
        background = _background_for_slide(output, slide_kind, use_gemini=use_ai_background, allow_mock_background=allow_mock_background)
        out_path = output / file_name
        if slide_kind == "face_map":
            slides.append(
                renderer(
                    photo_path=user_photo_path,
                    output_path=out_path,
                    user_name=user_name,
                    analysis_json=analysis_json,
                    background_path=background,
                    date_text=date_text,
                )
            )
        else:
            slides.append(
                renderer(
                    output_path=out_path,
                    user_name=user_name,
                    analysis_json=analysis_json,
                    background_path=background,
                )
            )
    logger.info("Generated protocol slides: %s", slides)
    return slides
