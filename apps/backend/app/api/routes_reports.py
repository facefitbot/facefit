from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, selectinload

from app.api.serializers import report_public_dict
from app.core.exceptions import not_found
from app.db.models import AnalysisRequest, BotSettings, CampaignSource, CtaClickEvent, GeneratedReport, ReportViewEvent
from app.db.repositories import get_bot_settings
from app.db.session import get_db

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/{token}")
def get_public_report(token: str, db: Session = Depends(get_db)) -> dict:
    report = (
        db.query(GeneratedReport)
        .options(
            selectinload(GeneratedReport.analysis).selectinload(AnalysisRequest.lead),
            selectinload(GeneratedReport.analysis).selectinload(AnalysisRequest.telegram_user),
            selectinload(GeneratedReport.analysis).selectinload(AnalysisRequest.images),
        )
        .filter(GeneratedReport.public_token == token, GeneratedReport.is_published.is_(True))
        .first()
    )
    if not report:
        raise not_found("Отчет не найден")
    settings = get_bot_settings(db)
    return report_public_dict(report, settings)


@router.post("/{token}/view")
def track_view(token: str, request: Request, db: Session = Depends(get_db)) -> dict:
    report = db.query(GeneratedReport).filter(GeneratedReport.public_token == token).first()
    if not report:
        raise not_found("Отчет не найден")
    report.opened_count += 1
    if report.analysis and report.analysis.lead:
        report.analysis.lead.report_opened = True
    db.add(
        ReportViewEvent(
            report_id=report.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )
    db.commit()
    return {"ok": True, "event": "report_opened"}


@router.post("/{token}/cta-click")
def track_cta(token: str, request: Request, db: Session = Depends(get_db)) -> dict:
    report = db.query(GeneratedReport).filter(GeneratedReport.public_token == token).first()
    if not report:
        raise not_found("Отчет не найден")
    settings: BotSettings = get_bot_settings(db)
    target = settings.whatsapp_url or settings.telegram_url or settings.instagram_url or ""
    report.cta_click_count += 1
    if report.analysis and report.analysis.lead:
        report.analysis.lead.cta_clicked = True
        if report.analysis.telegram_user and report.analysis.telegram_user.campaign:
            campaign: CampaignSource = report.analysis.telegram_user.campaign
            campaign.cta_clicks += 1
    db.add(
        CtaClickEvent(
            report_id=report.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            target_url=target,
        )
    )
    db.commit()
    return {"ok": True, "event": "cta_clicked", "target_url": target}
