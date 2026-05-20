from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.ai.openai_client import analyze_face, generate_personal_insights, generate_protocol_copy, generate_report_copy
from app.ai.prompts import REPORT_PROMPT, load_default_system_prompt
from app.ai.schemas import FaceAnalysis
from app.core.config import settings
from app.db.models import (
    AiJobLog,
    AnalysisRequest,
    AnalysisStatus,
    CampaignSource,
    FaceZone,
    GeneratedImage,
    GeneratedReport,
    SelectedProblem,
)
from app.db.repositories import get_bot_settings, get_prompt
from app.db.session import SessionLocal
from app.knowledge.retriever import retrieve_context
from app.reports.html_report import build_report_json, render_report_html
from app.reports.face_protocol_final import render_face_protocol_final_v1
from app.storage.local import local_storage
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _enqueue_progress_update(analysis_id: int, stage: str) -> None:
    try:
        from app.workers.tasks_telegram import enqueue_analysis_progress_update

        enqueue_analysis_progress_update(analysis_id, stage)
    except Exception:
        logger.warning("Could not enqueue Telegram progress update", exc_info=True)


def log_job(db: Session, analysis_id: int | None, stage: str, status: str, message: str | None = None, payload: dict | None = None) -> None:
    db.add(AiJobLog(analysis_id=analysis_id, stage=stage, status=status, message=message, payload=payload or {}))
    db.commit()


def _set_status(db: Session, analysis: AnalysisRequest, status: str) -> None:
    analysis.status = status
    if analysis.lead:
        analysis.lead.status = status
    if analysis.telegram_user:
        analysis.telegram_user.current_status = status
    db.commit()


def _sync_selected_problem_rows(db: Session, analysis: AnalysisRequest) -> None:
    db.query(SelectedProblem).filter(SelectedProblem.analysis_id == analysis.id).delete()
    for problem in analysis.selected_problems or []:
        db.add(SelectedProblem(analysis_id=analysis.id, slug=problem, title=problem))


def _persist_zones(db: Session, analysis: AnalysisRequest, zones: list[dict]) -> None:
    db.query(FaceZone).filter(FaceZone.analysis_id == analysis.id).delete()
    for zone in zones:
        db.add(
            FaceZone(
                analysis_id=analysis.id,
                number=zone.get("number", 0),
                name=zone.get("name", ""),
                status=zone.get("status", "attention"),
                color=zone.get("color", "yellow"),
                short_comment=zone.get("short_comment", ""),
                reason=zone.get("reason", ""),
                recommended_focus=zone.get("recommended_focus", ""),
            )
        )


def _relative_storage_path(abs_path: str) -> str:
    return Path(abs_path).resolve().relative_to(local_storage.root).as_posix()


def _sync_face_protocol_image_row(db: Session, analysis: AnalysisRequest, abs_path: str) -> None:
    db.query(GeneratedImage).filter(GeneratedImage.analysis_id == analysis.id, GeneratedImage.kind == "face_protocol_final").delete()
    db.add(
        GeneratedImage(
            analysis_id=analysis.id,
            kind="face_protocol_final",
            path=_relative_storage_path(abs_path),
            status="completed",
            metadata_json={"renderer": "face_protocol_final", "protocol_version": "final_v1"},
        )
    )


def regenerate_personal_insights_sync(db: Session, analysis: AnalysisRequest) -> dict:
    if not analysis.analysis_json:
        raise ValueError("У анализа нет analysis_json")
    knowledge_context = retrieve_context(db, analysis.selected_problems or [])
    system_prompt = get_prompt(db, "analysis_system", load_default_system_prompt())
    personal_insight_json = generate_personal_insights(
        analysis.analysis_json,
        analysis.selected_problems or [],
        knowledge_context,
        system_prompt,
    )
    analysis.personal_insight_json = personal_insight_json
    db.commit()
    log_job(db, analysis.id, "personal_insights", "success", "Personal insight JSON saved")
    return personal_insight_json


def regenerate_protocol_copy_sync(db: Session, analysis: AnalysisRequest) -> dict:
    if not analysis.analysis_json:
        raise ValueError("У анализа нет analysis_json")
    knowledge_context = retrieve_context(db, analysis.selected_problems or [])
    system_prompt = get_prompt(db, "analysis_system", load_default_system_prompt())
    personal_insight_json = regenerate_personal_insights_sync(db, analysis)
    protocol_copy_json = generate_protocol_copy(
        analysis.analysis_json,
        analysis.selected_problems or [],
        knowledge_context,
        system_prompt,
        personal_insight_json=personal_insight_json,
    )
    analysis.protocol_copy_json = protocol_copy_json
    analysis.face_protocol_version = "final_v1"
    analysis.protocol_version = "final_v1"
    db.commit()
    log_job(db, analysis.id, "protocol_copy", "success", "Protocol copy JSON regenerated")
    return protocol_copy_json


def regenerate_face_protocol_png_sync(db: Session, analysis: AnalysisRequest) -> str:
    if not analysis.original_photo_path:
        raise ValueError("У анализа нет исходного фото")
    protocol_copy_json = analysis.protocol_copy_json or regenerate_protocol_copy_sync(db, analysis)
    photo_abs = local_storage.abs_path(analysis.original_photo_path)
    protocol_dir_rel = f"protocols/final_v1/{analysis.id}"
    png_abs = render_face_protocol_final_v1(
        analysis_request_id=str(analysis.id),
        user_name=analysis.lead.name if analysis.lead else "Гость",
        user_photo_path_or_url=photo_abs,
        protocol_copy=protocol_copy_json,
        output_dir=local_storage.abs_path(protocol_dir_rel),
        created_at=analysis.created_at,
    )
    if not Path(png_abs).exists():
        raise RuntimeError("Expected final_v1 PNG was not generated")
    relative_png = _relative_storage_path(png_abs)
    analysis.face_protocol_version = "final_v1"
    analysis.face_protocol_image_path = relative_png
    analysis.protocol_version = "final_v1"
    analysis.protocol_image_path = relative_png
    analysis.protocol_image_url = None
    analysis.legacy_protocol_image_url = None
    analysis.protocol_slide_paths = []
    analysis.protocol_slide_copy = {}
    _sync_face_protocol_image_row(db, analysis, png_abs)
    db.commit()
    logger.info("Saved face protocol PNG: %s", png_abs)
    log_job(
        db,
        analysis.id,
        "face_protocol_final_v1",
        "success",
        relative_png,
        {"renderer": "face_protocol_final", "protocol_version": "final_v1"},
    )
    return png_abs


def _run_analysis_pipeline(analysis_id: int) -> None:
    db = SessionLocal()
    try:
        analysis = db.query(AnalysisRequest).filter(AnalysisRequest.id == analysis_id).first()
        if not analysis:
            return
        if not analysis.original_photo_path:
            raise ValueError("У анализа нет исходного фото")

        log_job(db, analysis.id, "pipeline", "started", "AI pipeline started")
        _set_status(db, analysis, AnalysisStatus.ANALYZING)
        _enqueue_progress_update(analysis.id, "analysis")

        photo_abs = local_storage.abs_path(analysis.original_photo_path)
        knowledge_context = retrieve_context(db, analysis.selected_problems or [])
        system_prompt = get_prompt(db, "analysis_system", load_default_system_prompt())
        ai_result = analyze_face(
            photo_abs,
            analysis.lead.name if analysis.lead else None,
            analysis.selected_problems or [],
            knowledge_context,
            system_prompt,
        )
        validated = FaceAnalysis.model_validate(ai_result).model_dump()
        analysis.analysis_json = validated
        _sync_selected_problem_rows(db, analysis)
        _persist_zones(db, analysis, validated.get("zones", []))
        db.commit()
        log_job(db, analysis.id, "openai_analysis", "success", "Structured JSON analysis saved", {"mock_mode": settings.ai_mock_mode})

        bot_settings = get_bot_settings(db)

        _set_status(db, analysis, AnalysisStatus.GENERATING_PROTOCOL)
        _enqueue_progress_update(analysis.id, "protocol_copy")
        logger.info("FACE_PROTOCOL_RENDERER=final_v1")
        try:
            personal_insight_json = generate_personal_insights(
                validated,
                analysis.selected_problems or [],
                knowledge_context,
                system_prompt,
            )
            analysis.personal_insight_json = personal_insight_json
            db.commit()
            log_job(db, analysis.id, "personal_insights", "success", "Personal insight JSON saved")
            protocol_copy_json = generate_protocol_copy(
                validated,
                analysis.selected_problems or [],
                knowledge_context,
                system_prompt,
                personal_insight_json=personal_insight_json,
            )
            analysis.protocol_copy_json = protocol_copy_json
            analysis.face_protocol_version = "final_v1"
            analysis.protocol_version = "final_v1"
            db.commit()
            log_job(db, analysis.id, "protocol_copy", "success", "Protocol copy JSON saved")
            _enqueue_progress_update(analysis.id, "render")
            protocol_png_abs = regenerate_face_protocol_png_sync(db, analysis)
        except Exception as exc:
            logger.error("Face protocol render failed", exc_info=True)
            analysis.status = AnalysisStatus.FAILED_PROTOCOL_RENDER
            analysis.error_message = str(exc)
            if analysis.lead:
                analysis.lead.status = AnalysisStatus.FAILED_PROTOCOL_RENDER
            if analysis.telegram_user:
                analysis.telegram_user.current_status = AnalysisStatus.FAILED_PROTOCOL_RENDER
            db.commit()
            log_job(db, analysis.id, "face_protocol_final_v1", "failed", str(exc))
            raise

        _set_status(db, analysis, AnalysisStatus.GENERATING_REPORT)
        _enqueue_progress_update(analysis.id, "report")
        report_prompt = get_prompt(db, "detailed_report", REPORT_PROMPT)
        report_extra = generate_report_copy(
            validated,
            analysis.selected_problems or [],
            knowledge_context,
            system_prompt=system_prompt,
            report_prompt=report_prompt,
            personal_insight_json=analysis.personal_insight_json or {},
        )
        report_json = build_report_json(analysis.lead.name if analysis.lead else "Гость", validated, analysis.selected_problems or [], report_extra)
        html = render_report_html(report_json)
        report = analysis.report or GeneratedReport(analysis_id=analysis.id, lead_id=analysis.lead_id)
        report.report_json = report_json
        report.html_content = html
        report.is_published = True
        db.add(report)
        analysis.report_json = report_json
        db.commit()
        db.refresh(report)
        if analysis.telegram_user and analysis.telegram_user.campaign:
            campaign: CampaignSource = analysis.telegram_user.campaign
            campaign.report_count += 1
        log_job(db, analysis.id, "report", "success", f"Public token: {report.public_token}")

        if bot_settings.manual_moderation_enabled:
            _set_status(db, analysis, AnalysisStatus.NEEDS_REVIEW)
        else:
            analysis.status = AnalysisStatus.COMPLETED
            analysis.completed_at = datetime.now(timezone.utc)
            if analysis.lead:
                analysis.lead.status = AnalysisStatus.COMPLETED
            if analysis.telegram_user:
                analysis.telegram_user.current_status = AnalysisStatus.COMPLETED
            db.commit()

        if not bot_settings.manual_moderation_enabled and analysis.telegram_user:
            report_url = f"{settings.public_app_url.rstrip('/')}/report/{report.public_token}"
            if analysis.face_protocol_version != "final_v1":
                raise RuntimeError("Expected final_v1 face protocol for new analysis")
            if not analysis.face_protocol_image_path:
                analysis.status = AnalysisStatus.FAILED_PROTOCOL_RENDER
                analysis.error_message = "Expected final_v1 PNG path was empty"
                db.commit()
                raise RuntimeError("Expected final_v1 PNG path was empty")
            protocol_png_abs = local_storage.abs_path(analysis.face_protocol_image_path)
            if not Path(protocol_png_abs).exists():
                logger.error("Face protocol PNG missing: %s", protocol_png_abs)
                analysis.status = AnalysisStatus.FAILED_PROTOCOL_RENDER
                analysis.error_message = "Expected final_v1 PNG was not found"
                if analysis.lead:
                    analysis.lead.status = AnalysisStatus.FAILED_PROTOCOL_RENDER
                if analysis.telegram_user:
                    analysis.telegram_user.current_status = AnalysisStatus.FAILED_PROTOCOL_RENDER
                db.commit()
                log_job(db, analysis.id, "telegram_send", "failed", "Expected final_v1 PNG was not found")
                raise RuntimeError("Expected final_v1 PNG was not found")
            from app.workers.tasks_telegram import enqueue_analysis_ready_message

            enqueue_analysis_ready_message(analysis.id, report_url)

        if not bot_settings.manual_moderation_enabled and bot_settings.after_photo_enabled and settings.enable_after_photo:
            from app.workers.tasks_after_photo import enqueue_after_photo

            enqueue_after_photo(analysis.id)

        log_job(db, analysis.id, "pipeline", "success", "AI pipeline completed")
    except Exception as exc:
        logger.exception("Analysis pipeline failed")
        analysis = db.query(AnalysisRequest).filter(AnalysisRequest.id == analysis_id).first()
        if analysis:
            if analysis.status != AnalysisStatus.FAILED_PROTOCOL_RENDER:
                analysis.status = AnalysisStatus.FAILED
            analysis.error_message = str(exc)
            if analysis.lead:
                analysis.lead.status = analysis.status
            if analysis.telegram_user:
                analysis.telegram_user.current_status = analysis.status
            db.commit()
        log_job(db, analysis_id, "pipeline", "failed", str(exc))
        raise
    finally:
        db.close()


@celery_app.task(
    name="app.workers.tasks_analysis.run_analysis_pipeline",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": settings.ai_retry_count},
    retry_backoff=True,
)
def run_analysis_pipeline(self, analysis_id: int) -> None:
    _run_analysis_pipeline(analysis_id)


def enqueue_analysis(analysis_id: int) -> None:
    try:
        run_analysis_pipeline.apply_async(args=[analysis_id], queue="analysis")
    except Exception:
        logger.warning("Celery broker unavailable, running analysis synchronously in current process")
        _run_analysis_pipeline(analysis_id)
