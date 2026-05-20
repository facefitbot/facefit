from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import AdminAuth
from app.db.models import (
    AiJobLog,
    AnalysisRequest,
    AnalysisStatus,
    CtaClickEvent,
    EventLog,
    GeneratedReport,
    Lead,
    ReportViewEvent,
    SelectedProblem,
    TelegramUser,
)
from app.db.session import get_db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
def stats(_: AdminAuth, db: Session = Depends(get_db)) -> dict:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=14)
    users = db.query(TelegramUser).count()
    leads = db.query(Lead).count()
    completed = db.query(AnalysisRequest).filter(AnalysisRequest.status == AnalysisStatus.COMPLETED).count()
    failed = db.query(AiJobLog).filter(AiJobLog.status == "failed").count()
    photo_count = db.query(AnalysisRequest).filter(AnalysisRequest.original_photo_path.is_not(None)).count()
    reports = db.query(GeneratedReport).count()
    opened = db.query(ReportViewEvent).count()
    cta = db.query(CtaClickEvent).count()

    by_day_rows = (
        db.query(func.date(AnalysisRequest.created_at).label("day"), func.count(AnalysisRequest.id))
        .filter(AnalysisRequest.created_at >= since)
        .group_by("day")
        .order_by("day")
        .all()
    )
    problems = (
        db.query(SelectedProblem.title, func.count(SelectedProblem.id))
        .group_by(SelectedProblem.title)
        .order_by(func.count(SelectedProblem.id).desc())
        .limit(8)
        .all()
    )
    events_by_source = (
        db.query(EventLog.payload["source"].astext.label("source"), func.count(EventLog.id))
        .filter(EventLog.event_type == "start", EventLog.payload["source"].astext.is_not(None))
        .group_by("source")
        .limit(10)
        .all()
        if db.bind and db.bind.dialect.name == "postgresql"
        else []
    )
    latest_leads = db.query(Lead).order_by(Lead.created_at.desc()).limit(8).all()
    return {
        "cards": {
            "users": users,
            "new_leads": leads,
            "completed_analyses": completed,
            "ai_errors": failed,
        },
        "conversion": {
            "start": users,
            "photo": photo_count,
            "analysis": completed,
            "report_opened": opened,
            "cta_clicked": cta,
            "start_to_photo": round(photo_count / users * 100, 2) if users else 0,
            "photo_to_analysis": round(completed / photo_count * 100, 2) if photo_count else 0,
            "analysis_to_report_opened": round(opened / reports * 100, 2) if reports else 0,
            "report_to_cta": round(cta / opened * 100, 2) if opened else 0,
        },
        "requests_by_day": [{"date": str(day), "count": count} for day, count in by_day_rows],
        "top_problems": [{"title": title, "count": count} for title, count in problems],
        "sources": [{"source": source or "unknown", "count": count} for source, count in events_by_source],
        "latest_leads": [
            {
                "id": lead.id,
                "name": lead.name,
                "status": lead.status,
                "created_at": lead.created_at,
                "selected_problems": lead.selected_problems or [],
            }
            for lead in latest_leads
        ],
    }

