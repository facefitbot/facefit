from __future__ import annotations

import logging
from pathlib import Path

from app.after_photo.generator import generate_after_photo_final
from app.after_photo.prompt_builder import build_after_photo_prompt
from app.core.config import settings
from app.db.models import AnalysisRequest, BotSettings, GeneratedImage
from app.db.session import SessionLocal
from app.storage.local import local_storage
from app.workers.celery_app import celery_app
from app.workers.tasks_analysis import log_job

logger = logging.getLogger(__name__)

AFTER_PHOTO_PROCESSING = "PROCESSING"
AFTER_PHOTO_APPROVED = "APPROVED"
AFTER_PHOTO_NEEDS_MANUAL_REVIEW = "NEEDS_MANUAL_REVIEW"
AFTER_PHOTO_FAILED = "FAILED"
AFTER_PHOTO_SKIPPED_NO_API_KEY = "SKIPPED_NO_API_KEY"


def _preferred_intensity(db, explicit_intensity: str | None) -> str:
    if explicit_intensity in {"subtle", "balanced", "visible"}:
        return explicit_intensity
    bot_settings = db.query(BotSettings).first()
    ai_settings = bot_settings.ai_settings if bot_settings and isinstance(bot_settings.ai_settings, dict) else {}
    configured = ai_settings.get("after_photo_default_intensity") or settings.after_photo_default_intensity
    return configured if configured in {"subtle", "balanced", "visible"} else "balanced"


def _persist_result(db, analysis: AnalysisRequest, result: dict, prompt_payload: dict) -> None:
    variant_paths = result.get("variant_paths") or []
    quality_results = result.get("quality_results") or []
    final_path = result.get("final_path")
    status = result.get("status") or AFTER_PHOTO_FAILED

    analysis.after_photo_status = status
    analysis.after_photo_variant_paths = variant_paths
    analysis.after_photo_final_path = final_path
    analysis.after_photo_quality_results = quality_results
    analysis.after_photo_used_intensity = result.get("used_intensity")
    analysis.after_photo_retry_count = int(result.get("retry_count") or 0)
    analysis.after_photo_path = final_path if status == AFTER_PHOTO_APPROVED else None
    analysis.after_photo_variants = [
        {
            "index": index,
            "path": path,
            "status": "generated",
        }
        for index, path in enumerate(variant_paths, start=1)
    ]
    analysis.after_photo_plan = {
        "legacy": False,
        "pipeline": "universal_prompt_v1",
        "prompt_source": "universal_base_prompt",
        "provider": settings.after_photo_provider,
        "image_model": (
            (settings.openai_after_photo_image_model or settings.openai_protocol_image_model or "gpt-image-2")
            if settings.after_photo_provider == "openai"
            else settings.replicate_flux_model
        ),
        "intensity": result.get("used_intensity"),
        "negative_prompt": prompt_payload.get("negative_prompt"),
        "variant_count": settings.after_photo_variant_count,
        "retry_count": result.get("retry_count") or 0,
        "reason": result.get("reason") or "",
    }

    image = (
        db.query(GeneratedImage)
        .filter(GeneratedImage.analysis_id == analysis.id, GeneratedImage.kind == "after_photo")
        .order_by(GeneratedImage.id.desc())
        .first()
    )
    if not image:
        image = GeneratedImage(analysis_id=analysis.id, kind="after_photo")
        db.add(image)
    image.status = "completed" if status == AFTER_PHOTO_APPROVED else status.lower()
    image.path = final_path
    image.prompt = prompt_payload.get("prompt")
    image.negative_prompt = prompt_payload.get("negative_prompt")
    image.metadata_json = {
        "pipeline": "universal_prompt_v1",
        "status": status,
        "variant_paths": variant_paths,
        "quality_results": quality_results,
        "used_intensity": result.get("used_intensity"),
        "used_retry": result.get("used_retry"),
        "retry_count": result.get("retry_count"),
        "reason": result.get("reason"),
    }


def _generate_after_photo(analysis_id: int, preferred_intensity: str | None = None) -> None:
    db = SessionLocal()
    try:
        analysis = db.query(AnalysisRequest).filter(AnalysisRequest.id == analysis_id).first()
        if not analysis or not analysis.original_photo_path:
            raise ValueError("Анализ не найден или нет исходного фото")

        intensity = _preferred_intensity(db, preferred_intensity)
        prompt_payload = build_after_photo_prompt(intensity)
        logger.info("AFTER_PHOTO_PIPELINE=universal_prompt_v1")
        logger.info("Selected intensity: %s", intensity)

        analysis.after_photo_status = AFTER_PHOTO_PROCESSING
        analysis.after_photo_used_intensity = intensity
        analysis.after_photo_retry_count = 0
        analysis.after_photo_plan = {
            "legacy": False,
            "pipeline": "universal_prompt_v1",
            "prompt_source": "universal_base_prompt",
            "provider": settings.after_photo_provider,
            "image_model": (
                (settings.openai_after_photo_image_model or settings.openai_protocol_image_model or "gpt-image-2")
                if settings.after_photo_provider == "openai"
                else settings.replicate_flux_model
            ),
            "intensity": intensity,
            "variant_count": settings.after_photo_variant_count,
            "negative_prompt": prompt_payload.get("negative_prompt"),
        }
        db.commit()

        input_abs = local_storage.abs_path(analysis.original_photo_path)
        result = generate_after_photo_final(
            analysis_request_id=str(analysis.id),
            original_photo_path=input_abs,
            preferred_intensity=intensity,
        )
        _persist_result(db, analysis, result, prompt_payload)
        db.commit()

        log_job(
            db,
            analysis.id,
            "after_photo",
            "success" if result.get("status") == AFTER_PHOTO_APPROVED else "manual_review",
            result.get("final_path") or result.get("status") or "",
            result,
        )

        if analysis.telegram_user:
            from app.workers.tasks_telegram import (
                enqueue_after_photo_message,
                enqueue_after_photo_pending_message,
                enqueue_after_photo_retry_message,
            )

            if result.get("status") == AFTER_PHOTO_APPROVED and result.get("final_path"):
                enqueue_after_photo_message(analysis.id)
            elif result.get("status") == AFTER_PHOTO_FAILED:
                enqueue_after_photo_retry_message(analysis.id)
            elif result.get("status") == AFTER_PHOTO_NEEDS_MANUAL_REVIEW:
                enqueue_after_photo_pending_message(analysis.id)
    except Exception as exc:
        logger.exception("After-photo generation failed")
        analysis = db.query(AnalysisRequest).filter(AnalysisRequest.id == analysis_id).first()
        if analysis:
            analysis.after_photo_status = AFTER_PHOTO_FAILED
            analysis.after_photo_plan = {
                "legacy": False,
                "pipeline": "universal_prompt_v1",
                "error": str(exc),
            }
            image = GeneratedImage(analysis_id=analysis_id, kind="after_photo", status="failed", metadata_json={"error": str(exc)})
            db.add(image)
            db.commit()
        log_job(db, analysis_id, "after_photo", "failed", str(exc))
    finally:
        db.close()


@celery_app.task(
    name="app.workers.tasks_after_photo.generate_after_photo_task",
    bind=True,
    autoretry_for=(),
    retry_kwargs={"max_retries": settings.after_photo_retry_count},
    retry_backoff=True,
)
def generate_after_photo_task(self, analysis_id: int, preferred_intensity: str | None = None) -> None:
    _generate_after_photo(analysis_id, preferred_intensity)


def enqueue_after_photo(analysis_id: int, preferred_intensity: str | None = None) -> None:
    try:
        generate_after_photo_task.apply_async(args=[analysis_id, preferred_intensity], queue="after_photo")
    except Exception:
        _generate_after_photo(analysis_id, preferred_intensity)
