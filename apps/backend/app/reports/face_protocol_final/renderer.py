from __future__ import annotations

import base64
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.ai.prompts import DISCLAIMER
from app.core.config import settings
from app.reports.face_protocol_final.normalize import normalize_protocol_copy

logger = logging.getLogger(__name__)

CANVAS_WIDTH = 1080
RENDER_ZOOM = 0.84
RENDER_LAYOUT_WIDTH = CANVAS_WIDTH / RENDER_ZOOM
LEGACY_RENDERER_ERROR = "LEGACY_FACE_PROTOCOL_RENDERER_DISABLED_USE_FINAL_V1"

STATUS_VISUALS = {
    "good": {"fill": "var(--good-soft)", "stroke": "var(--good)", "pill_class": ""},
    "attention": {"fill": "var(--attention-soft)", "stroke": "var(--attention)", "pill_class": "attn"},
    "priority": {"fill": "var(--priority-soft)", "stroke": "var(--priority)", "pill_class": "prio"},
}

DEFAULT_ZONE_SHAPES = {
    1: "forehead",
    2: "glabella",
    3: "eyes",
    4: "nasolabial",
    5: "mouth",
    6: "jawline",
}

ZONE_NUMBER_POSITIONS = {
    "forehead": (150, 84),
    "glabella": (150, 132),
    "eyes": (116, 148),
    "puffiness": (116, 168),
    "nasolabial": (178, 218),
    "cheeks": (192, 195),
    "mouth": (150, 224),
    "jawline": (214, 252),
    "chin": (150, 260),
    "neck": (196, 330),
}

MONTHS_RU = {
    1: "ЯНВАРЯ",
    2: "ФЕВРАЛЯ",
    3: "МАРТА",
    4: "АПРЕЛЯ",
    5: "МАЯ",
    6: "ИЮНЯ",
    7: "ИЮЛЯ",
    8: "АВГУСТА",
    9: "СЕНТЯБРЯ",
    10: "ОКТЯБРЯ",
    11: "НОЯБРЯ",
    12: "ДЕКАБРЯ",
}


def _module_dir() -> Path:
    return Path(__file__).resolve().parent


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_module_dir()),
        autoescape=select_autoescape(("html", "xml")),
    )


def _format_date(value: Any) -> str:
    if isinstance(value, datetime):
        return f"{value.day} {MONTHS_RU[value.month]} {value.year}"
    if hasattr(value, "strftime"):
        try:
            return value.strftime("%d.%m.%Y")
        except Exception:
            pass
    if value:
        return str(value)
    now = datetime.now()
    return f"{now.day} {MONTHS_RU[now.month]} {now.year}"


def _fallback_photo_data_uri() -> str:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="900" height="1200" viewBox="0 0 900 1200">
<defs>
<radialGradient id="skin" cx="50%" cy="38%" r="62%">
<stop offset="0%" stop-color="#f6e0cb"/>
<stop offset="58%" stop-color="#e8c8aa"/>
<stop offset="100%" stop-color="#c9a487"/>
</radialGradient>
</defs>
<rect width="900" height="1200" fill="url(#skin)"/>
<ellipse cx="450" cy="500" rx="235" ry="310" fill="#edd0b6" opacity=".55"/>
<path d="M260 860 Q450 1040 640 860" fill="none" stroke="#b99076" stroke-width="20" stroke-linecap="round" opacity=".22"/>
</svg>"""
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _photo_url(photo: str | None) -> str:
    if photo and photo.startswith(("http://", "https://", "data:")):
        return photo
    if photo:
        path = Path(photo).expanduser()
        candidates = [path]
        if not path.is_absolute():
            candidates.extend([
                settings.storage_root() / photo,
                _project_root() / "storage" / photo,
            ])
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve().as_uri()
    logger.warning("Using fallback face photo placeholder")
    return _fallback_photo_data_uri()


def _score_percent(score: str) -> int:
    match = re.search(r"\d{1,3}", score or "")
    if not match:
        return 78
    return max(0, min(100, int(match.group(0))))


def _apply_render_scale(html: str) -> str:
    render_css = f"""
  /* Render-only scale: keeps the provided journal layout intact while producing a 1080px-wide PNG around 1500px tall. */
  .sheet {{
    width: {RENDER_LAYOUT_WIDTH:.3f}px;
    zoom: {RENDER_ZOOM};
  }}
"""
    return html.replace("</style>", f"{render_css}</style>", 1)


def _zone_visual(status: str) -> dict[str, str]:
    return STATUS_VISUALS.get(status, STATUS_VISUALS["attention"])


def _zone_shape(label: str, fallback_index: int) -> str:
    normalized = (label or "").lower()
    if "лоб" in normalized:
        return "forehead"
    if "меж" in normalized:
        return "glabella"
    if "отеч" in normalized or "отёч" in normalized or "мешк" in normalized:
        return "puffiness"
    if "глаз" in normalized or "век" in normalized:
        return "eyes"
    if "носог" in normalized:
        return "nasolabial"
    if "скул" in normalized:
        return "cheeks"
    if "овал" in normalized or "бры" in normalized or "контур" in normalized:
        return "jawline"
    if "подбор" in normalized:
        return "chin"
    if "ше" in normalized:
        return "neck"
    if "рот" in normalized or "губ" in normalized or "периорал" in normalized:
        return "mouth"
    return DEFAULT_ZONE_SHAPES.get(fallback_index, "jawline")


def _map_zones(zones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for index, zone in enumerate(zones, start=1):
        shape = _zone_shape(str(zone.get("label", "")), index)
        num_x, num_y = ZONE_NUMBER_POSITIONS.get(shape, ZONE_NUMBER_POSITIONS["jawline"])
        result.append(
            {
                **zone,
                "shape": shape,
                "visual": _zone_visual(zone.get("status", "attention")),
                "num_x": num_x,
                "num_y": num_y,
            }
        )
    return result


def _context(
    *,
    user_name: str,
    photo_url: str,
    protocol_copy: dict[str, Any],
    created_at: Any,
    disclaimer: str | None = None,
) -> dict[str, Any]:
    zones = protocol_copy["zones"][:6]
    zone_visuals = [_zone_visual(zone.get("status", "attention")) for zone in zones]
    growth_zones = [
        {
            **zone,
            "pill_class": _zone_visual(zone.get("status", "attention"))["pill_class"],
        }
        for zone in protocol_copy["growth_zones"][:5]
    ]
    skin_age = protocol_copy["skin_age"]
    skin_type = protocol_copy["skin_type"]
    face_aging = protocol_copy["face_aging"]
    return {
        "user_name": user_name or "Гость",
        "analysis_date": _format_date(created_at),
        "photo_url": photo_url,
        "skin_age_value": skin_age["value"],
        "skin_age_unit": skin_age["unit"],
        "skin_age_comment": skin_age["comment"],
        "skin_score": skin_age["score"],
        "skin_score_percent": _score_percent(skin_age["score"]),
        "skin_type_title": skin_type["title"],
        "skin_type_bullets": skin_type["bullets"],
        "face_type": face_aging["face_type"],
        "aging_type": face_aging["aging_type"],
        "aging_bullets": face_aging["bullets"],
        "aging_forecast": face_aging.get("forecast", []),
        "aging_strong_base": face_aging.get("strong_base", ""),
        "zones": zones,
        "zone_visuals": zone_visuals,
        "map_zones": _map_zones(zones),
        "causes": protocol_copy["causes"],
        "why_intro": protocol_copy.get("why_intro", ""),
        "why_outro": protocol_copy.get("why_outro", ""),
        "strengths": protocol_copy["strengths"],
        "benefits": protocol_copy["benefits"],
        "benefits_outro": protocol_copy.get("benefits_outro", ""),
        "forecast": protocol_copy["forecast"],
        "growth_zones": growth_zones,
        "final_summary": protocol_copy["final_summary"],
        "disclaimer": disclaimer or DISCLAIMER,
    }


def _chromium_executable_path() -> str | None:
    executable_path = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
    if executable_path:
        return executable_path
    for candidate in (
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ):
        if Path(candidate).exists():
            return candidate
    return None


def _screenshot_sheet(html_path: Path, output_path: Path) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is required for face_protocol_final. Install playwright and Chromium.") from exc

    executable_path = _chromium_executable_path()
    with sync_playwright() as playwright:
        launch_kwargs: dict[str, Any] = {"args": ["--no-sandbox", "--disable-dev-shm-usage"]}
        if executable_path:
            launch_kwargs["executable_path"] = executable_path
        browser = playwright.chromium.launch(**launch_kwargs)
        page = browser.new_page(viewport={"width": CANVAS_WIDTH, "height": 2200}, device_scale_factor=1)
        page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
        sheet = page.locator(".sheet")
        sheet.wait_for(state="visible", timeout=15_000)
        sheet.screenshot(path=str(output_path), type="png")
        browser.close()


def render_face_protocol_final_v1(
    analysis_request_id: str,
    user_name: str,
    user_photo_path_or_url: str,
    protocol_copy: dict,
    output_dir: str,
    created_at,
) -> str:
    logger.info("FACE_PROTOCOL_RENDERER=final_v1")
    logger.info("Rendering face protocol from template.html")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    try:
        normalized = normalize_protocol_copy(protocol_copy)
        logger.info("Protocol copy normalized")
        html = _apply_render_scale(_env().get_template("template.html").render(
            **_context(
                user_name=user_name,
                photo_url=_photo_url(user_photo_path_or_url),
                protocol_copy=normalized,
                created_at=created_at,
            )
        ))
        safe_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(analysis_request_id)).strip("_") or "preview"
        html_path = output / f"face_protocol_final_v1_{safe_id}.html"
        png_path = output / f"face_protocol_final_v1_{safe_id}.png"
        html_path.write_text(html, encoding="utf-8")
        _screenshot_sheet(html_path, png_path)
        logger.info("Saved face protocol PNG: %s", png_path)
        return str(png_path)
    except Exception:
        logger.error("Face protocol render failed", exc_info=True)
        raise
