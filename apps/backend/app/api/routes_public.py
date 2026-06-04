from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings as env_settings
from app.core.exceptions import not_found
from app.db.crm import add_lead_event
from app.db.models import ClientStatus, CtaClickEvent, GeneratedReport, ReportViewEvent
from app.db.repositories import get_bot_settings
from app.db.session import get_db
from app.reports.web_report_v6 import render_bella_web_report_v6_html

router = APIRouter(tags=["public"])


@router.get("/report/{token}", response_class=HTMLResponse)
def public_report_page(token: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    report = db.query(GeneratedReport).filter(GeneratedReport.public_token == token, GeneratedReport.is_published.is_(True)).first()
    if not report:
        raise not_found("Отчет не найден")

    bot_settings = get_bot_settings(db)
    report.opened_count += 1
    if report.analysis and report.analysis.lead:
        report.analysis.lead.report_opened = True
        if report.analysis.lead.crm_status not in {ClientStatus.CTA_CLICKED, ClientStatus.PAID, ClientStatus.BOUGHT}:
            report.analysis.lead.crm_status = ClientStatus.REPORT_OPENED
        add_lead_event(db, report.analysis.lead, "report_opened", "Пользователь открыл отчет", {"report_id": report.id})
    db.add(
        ReportViewEvent(
            report_id=report.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )
    db.commit()
    return HTMLResponse(
        render_bella_web_report_v6_html(report, bot_settings),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@router.get("/report/{token}/cta")
def public_report_cta(token: str, request: Request, db: Session = Depends(get_db)):
    report = db.query(GeneratedReport).filter(GeneratedReport.public_token == token, GeneratedReport.is_published.is_(True)).first()
    if not report:
        raise not_found("Отчет не найден")

    bot_settings = get_bot_settings(db)
    target = bot_settings.whatsapp_url or bot_settings.telegram_url or bot_settings.instagram_url or env_settings.public_app_url or "/"
    report.cta_click_count += 1
    if report.analysis and report.analysis.lead:
        report.analysis.lead.cta_clicked = True
        report.analysis.lead.crm_status = ClientStatus.CTA_CLICKED
        add_lead_event(db, report.analysis.lead, "cta_clicked", "Пользователь нажал CTA", {"report_id": report.id, "target_url": target})
    db.add(
        CtaClickEvent(
            report_id=report.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            target_url=target,
        )
    )
    db.commit()
    return RedirectResponse(target)
