from __future__ import annotations

import logging

from app.ai.openai_client import generate_report_copy
from app.ai.prompts import REPORT_PROMPT, load_default_system_prompt
from app.db.models import AnalysisRequest, GeneratedReport
from app.db.repositories import get_prompt
from app.db.session import SessionLocal
from app.knowledge.retriever import retrieve_context
from app.reports.html_report import build_report_json, render_report_html
from app.workers.celery_app import celery_app
from app.workers.tasks_analysis import log_job, regenerate_personal_insights_sync

logger = logging.getLogger(__name__)


def _regenerate_report(analysis_id: int) -> None:
    db = SessionLocal()
    try:
        analysis = db.query(AnalysisRequest).filter(AnalysisRequest.id == analysis_id).first()
        if not analysis or not analysis.analysis_json:
            raise ValueError("Анализ не найден или JSON анализа пустой")
        knowledge_context = retrieve_context(db, analysis.selected_problems or [])
        system_prompt = get_prompt(db, "analysis_system", load_default_system_prompt())
        report_prompt = get_prompt(db, "detailed_report", REPORT_PROMPT)
        personal_insight_json = analysis.personal_insight_json or regenerate_personal_insights_sync(db, analysis)
        extra = generate_report_copy(
            analysis.analysis_json,
            analysis.selected_problems or [],
            knowledge_context,
            system_prompt=system_prompt,
            report_prompt=report_prompt,
            personal_insight_json=personal_insight_json,
        )
        report_json = build_report_json(analysis.lead.name if analysis.lead else "Гость", analysis.analysis_json, analysis.selected_problems or [], extra)
        report = analysis.report or GeneratedReport(analysis_id=analysis.id, lead_id=analysis.lead_id)
        report.report_json = report_json
        report.html_content = render_report_html(report_json)
        report.is_published = True
        analysis.report_json = report_json
        db.add(report)
        db.commit()
        log_job(db, analysis.id, "regenerate_report", "success", "Report regenerated")
    except Exception as exc:
        logger.exception("Report regeneration failed")
        log_job(db, analysis_id, "regenerate_report", "failed", str(exc))
        raise
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks_report.regenerate_report_task", bind=True)
def regenerate_report_task(self, analysis_id: int) -> None:
    _regenerate_report(analysis_id)


def enqueue_report(analysis_id: int) -> None:
    try:
        regenerate_report_task.apply_async(args=[analysis_id], queue="report")
    except Exception:
        _regenerate_report(analysis_id)
