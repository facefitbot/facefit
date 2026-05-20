from __future__ import annotations

import base64
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.reports.protocol_v3.schema import normalize_protocol_slide_copy

logger = logging.getLogger(__name__)
LEGACY_RENDERER_ERROR = "LEGACY_FACE_PROTOCOL_RENDERER_DISABLED_USE_FINAL_V1"

CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
WATERMARK = "PROTOCOL V3 ACTIVE"


STATUS_THEME = {
    "good": {"name": "Все хорошо", "class": "status-good", "fill": "rgba(126, 164, 139, 0.18)", "stroke": "#7EA48B"},
    "attention": {"name": "Зона внимания", "class": "status-attention", "fill": "rgba(210, 175, 85, 0.20)", "stroke": "#D2AF55"},
    "priority": {"name": "Приоритет", "class": "status-priority", "fill": "rgba(185, 108, 124, 0.20)", "stroke": "#B96C7C"},
}

SHAPE_LAYOUT = {
    "forehead": {"label": (43, 12), "line": (52, 18), "shapes": [{"kind": "ellipse", "cx": 50, "cy": 19, "rx": 27, "ry": 9}]},
    "glabella": {"label": (58, 26), "line": (51, 31), "shapes": [{"kind": "rect", "x": 46, "y": 24, "w": 9, "h": 17, "rx": 5}]},
    "eyes": {
        "label": (8, 34),
        "line": (35, 42),
        "shapes": [
            {"kind": "ellipse", "cx": 33, "cy": 39, "rx": 17, "ry": 8},
            {"kind": "ellipse", "cx": 67, "cy": 39, "rx": 17, "ry": 8},
            {"kind": "ellipse", "cx": 33, "cy": 47, "rx": 15, "ry": 6},
            {"kind": "ellipse", "cx": 67, "cy": 47, "rx": 15, "ry": 6},
        ],
    },
    "nasolabial": {
        "label": (60, 50),
        "line": (58, 55),
        "shapes": [
            {"kind": "rect", "x": 39, "y": 48, "w": 8, "h": 25, "rx": 5, "rotate": -12},
            {"kind": "rect", "x": 61, "y": 48, "w": 8, "h": 25, "rx": 5, "rotate": 12},
        ],
    },
    "cheeks": {
        "label": (8, 52),
        "line": (30, 55),
        "shapes": [
            {"kind": "path", "d": "M25 50 C32 43 44 46 43 58 C42 68 30 70 24 62 C20 57 21 53 25 50Z"},
            {"kind": "path", "d": "M75 50 C68 43 56 46 57 58 C58 68 70 70 76 62 C80 57 79 53 75 50Z"},
        ],
    },
    "jawline": {
        "label": (70, 68),
        "line": (72, 68),
        "shapes": [{"kind": "path", "d": "M24 68 C30 83 42 89 50 89 C58 89 70 83 76 68 L71 76 C62 85 38 85 29 76Z"}],
    },
    "chin": {"label": (37, 76), "line": (50, 77), "shapes": [{"kind": "ellipse", "cx": 50, "cy": 76, "rx": 14, "ry": 8}]},
    "neck": {"label": (58, 88), "line": (54, 88), "shapes": [{"kind": "path", "d": "M37 84 C45 88 55 88 63 84 L68 99 L32 99Z"}]},
    "puffiness": {
        "label": (8, 64),
        "line": (35, 49),
        "shapes": [
            {"kind": "ellipse", "cx": 34, "cy": 48, "rx": 14, "ry": 6},
            {"kind": "ellipse", "cx": 66, "cy": 48, "rx": 14, "ry": 6},
        ],
    },
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _module_dir() -> Path:
    return Path(__file__).resolve().parent


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_module_dir() / "templates"),
        autoescape=select_autoescape(("html", "xml")),
    )


def _css() -> str:
    return (_module_dir() / "static" / "protocol.css").read_text(encoding="utf-8")


def _image_src(photo: str) -> str:
    if photo.startswith(("http://", "https://", "data:")):
        return photo
    path = Path(photo).expanduser()
    if not path.exists():
        storage_candidate = _project_root() / "storage" / photo
        if storage_candidate.exists():
            path = storage_candidate
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _zone_views(copy: dict[str, Any]) -> list[dict[str, Any]]:
    views: list[dict[str, Any]] = []
    for zone in copy["face_map"]["zones"]:
        status = zone.get("status", "attention")
        theme = STATUS_THEME.get(status, STATUS_THEME["attention"])
        shape = zone.get("shape", "forehead")
        layout = SHAPE_LAYOUT.get(shape, SHAPE_LAYOUT["forehead"])
        views.append(
            {
                **zone,
                "status_name": theme["name"],
                "status_class": theme["class"],
                "fill": theme["fill"],
                "stroke": theme["stroke"],
                "label_x": layout["label"][0],
                "label_y": layout["label"][1],
                "line_x": layout["line"][0],
                "line_y": layout["line"][1],
                "shapes": layout["shapes"],
            }
        )
    return views


def _render_html(template_name: str, context: dict[str, Any]) -> str:
    return _env().get_template(template_name).render(**context)


def _screenshot_html(html: str, output_path: Path) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - exercised in deployment if dependency is missing.
        raise RuntimeError("Playwright is required for protocol_v3. Run `pip install playwright` and `python -m playwright install chromium`.") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    executable_path = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
    if not executable_path:
        for candidate in ("/usr/bin/chromium", "/usr/bin/chromium-browser", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
            if Path(candidate).exists():
                executable_path = candidate
                break
    with sync_playwright() as playwright:
        launch_kwargs: dict[str, Any] = {"args": ["--no-sandbox", "--disable-dev-shm-usage"]}
        if executable_path:
            launch_kwargs["executable_path"] = executable_path
        browser = playwright.chromium.launch(**launch_kwargs)
        page = browser.new_page(viewport={"width": CANVAS_WIDTH, "height": CANVAS_HEIGHT}, device_scale_factor=1)
        page.set_content(html, wait_until="networkidle")
        page.screenshot(path=str(output_path), full_page=False, type="png")
        browser.close()


def render_face_protocol_v3(
    analysis_request_id: str,
    user_name: str,
    user_photo_url_or_path: str,
    protocol_slide_copy: dict[str, Any],
    output_dir: str,
    created_at: datetime,
) -> list[str]:
    raise RuntimeError(LEGACY_RENDERER_ERROR)
    logger.warning("PROTOCOL_V3_RENDERER_ACTIVE")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    normalized = normalize_protocol_slide_copy(protocol_slide_copy)
    photo_src = _image_src(user_photo_url_or_path)
    date_value = created_at.strftime("%d.%m.%Y") if hasattr(created_at, "strftime") else str(created_at)
    context = {
        "css": _css(),
        "copy": normalized,
        "zones": _zone_views(normalized),
        "legend": [STATUS_THEME["good"], STATUS_THEME["attention"], STATUS_THEME["priority"]],
        "user_name": user_name or "Гость",
        "date": date_value,
        "photo_src": photo_src,
        "watermark": WATERMARK,
    }

    templates = [
        ("slide_1_face_map.html", f"protocol_v3_{analysis_request_id}_slide_1.png"),
        ("slide_2_summary.html", f"protocol_v3_{analysis_request_id}_slide_2.png"),
        ("slide_3_plan.html", f"protocol_v3_{analysis_request_id}_slide_3.png"),
    ]
    slide_paths: list[str] = []
    for template_name, filename in templates:
        path = output / filename
        html = _render_html(template_name, context)
        (output / filename.replace(".png", ".html")).write_text(html, encoding="utf-8")
        _screenshot_html(html, path)
        slide_paths.append(str(path))
    logger.info("Generated protocol_v3 slides: %s", slide_paths)
    return slide_paths
