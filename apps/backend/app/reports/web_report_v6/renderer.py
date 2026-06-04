from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.db.models import BotSettings, GeneratedReport
from app.reports.web_report_v6.view_model import (
    WEB_REPORT_V6_VERSION,
    build_bella_web_report_v6_view_model,
    buildBellaWebReportV6ViewModel,
)


logger = logging.getLogger(__name__)
TEMPLATE_PATH = Path(__file__).resolve().parent / "template.html"


def build_bella_web_report_v6_data(report: GeneratedReport, settings: BotSettings) -> dict[str, Any]:
    view_model = build_bella_web_report_v6_view_model(report=report, settings=settings)
    quality = view_model.get("quality") if isinstance(view_model.get("quality"), dict) else {}
    if quality.get("passed"):
        logger.info(
            "bella_web_report_v6_quality_passed report_id=%s aging_type=%s warnings=%s",
            report.id,
            (view_model.get("source_trace") or {}).get("aging_type"),
            quality.get("warnings") or [],
        )
    else:
        logger.warning(
            "bella_web_report_v6_quality_failed report_id=%s aging_type=%s errors=%s warnings=%s",
            report.id,
            (view_model.get("source_trace") or {}).get("aging_type"),
            quality.get("errors") or [],
            quality.get("warnings") or [],
        )
    return view_model


def render_bella_web_report_v6_template(view_model: dict[str, Any], *, token: str = "") -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    data_json = json.dumps(view_model, ensure_ascii=False).replace("</", "<\\/")
    token_json = json.dumps(token or "", ensure_ascii=False)
    return template.replace("__REPORT_DATA_JSON__", data_json).replace("__REPORT_TOKEN_JSON__", token_json)


def render_bella_web_report_v6_html(report: GeneratedReport, settings: BotSettings) -> str:
    return render_bella_web_report_v6_template(
        build_bella_web_report_v6_data(report, settings),
        token=report.public_token or "",
    )


__all__ = [
    "WEB_REPORT_V6_VERSION",
    "build_bella_web_report_v6_data",
    "build_bella_web_report_v6_view_model",
    "buildBellaWebReportV6ViewModel",
    "render_bella_web_report_v6_html",
    "render_bella_web_report_v6_template",
]
