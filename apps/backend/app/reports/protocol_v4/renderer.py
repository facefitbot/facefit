from __future__ import annotations

import base64
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.reports.protocol_v4.schema import normalize_protocol_slide_copy

logger = logging.getLogger(__name__)
LEGACY_RENDERER_ERROR = "LEGACY_FACE_PROTOCOL_RENDERER_DISABLED_USE_FINAL_V1"

CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350

STATUS_THEME = {
    "good": {"name": "Все хорошо", "class": "status-good", "stroke": "#7EA48B", "fill": "rgba(126, 164, 139, 0.045)"},
    "attention": {"name": "Зона внимания", "class": "status-attention", "stroke": "#D6B45D", "fill": "rgba(214, 180, 93, 0.055)"},
    "priority": {"name": "Приоритет", "class": "status-priority", "stroke": "#B96C7C", "fill": "rgba(185, 108, 124, 0.06)"},
}

RAIL_LAYOUT = {
    "forehead": {"rail": "left", "top": 12, "anchor": (48, 18), "line": (24, 18), "shape": [{"kind": "ellipse", "cx": 50, "cy": 18, "rx": 24, "ry": 7}]},
    "glabella": {"rail": "right", "top": 18, "anchor": (51, 31), "line": (76, 24), "shape": [{"kind": "rect", "x": 47, "y": 24, "w": 7, "h": 15, "rx": 4}]},
    "eyes": {
        "rail": "left",
        "top": 34,
        "anchor": (34, 40),
        "line": (24, 39),
        "shape": [
            {"kind": "ellipse", "cx": 34, "cy": 39, "rx": 14, "ry": 6},
            {"kind": "ellipse", "cx": 66, "cy": 39, "rx": 14, "ry": 6},
            {"kind": "ellipse", "cx": 34, "cy": 47, "rx": 13, "ry": 4},
            {"kind": "ellipse", "cx": 66, "cy": 47, "rx": 13, "ry": 4},
        ],
    },
    "nasolabial": {
        "rail": "right",
        "top": 42,
        "anchor": (61, 56),
        "line": (76, 46),
        "shape": [
            {"kind": "path", "d": "M41 48 C37 57 39 66 44 73"},
            {"kind": "path", "d": "M59 48 C63 57 61 66 56 73"},
        ],
    },
    "cheeks": {
        "rail": "left",
        "top": 57,
        "anchor": (31, 58),
        "line": (24, 60),
        "shape": [
            {"kind": "path", "d": "M24 54 C30 48 43 50 42 61 C41 68 30 70 24 63 C21 60 21 57 24 54Z"},
            {"kind": "path", "d": "M76 54 C70 48 57 50 58 61 C59 68 70 70 76 63 C79 60 79 57 76 54Z"},
        ],
    },
    "jawline": {"rail": "right", "top": 62, "anchor": (72, 72), "line": (76, 66), "shape": [{"kind": "path", "d": "M24 70 C31 84 42 90 50 90 C58 90 69 84 76 70"}]},
    "chin": {"rail": "left", "top": 78, "anchor": (50, 77), "line": (24, 80), "shape": [{"kind": "ellipse", "cx": 50, "cy": 77, "rx": 12, "ry": 5}]},
    "neck": {"rail": "right", "top": 81, "anchor": (54, 88), "line": (76, 84), "shape": [{"kind": "path", "d": "M38 84 C46 88 54 88 62 84 L66 99 L34 99Z"}]},
    "puffiness": {
        "rail": "left",
        "top": 34,
        "anchor": (34, 47),
        "line": (24, 42),
        "shape": [
            {"kind": "ellipse", "cx": 34, "cy": 47, "rx": 12, "ry": 4},
            {"kind": "ellipse", "cx": 66, "cy": 47, "rx": 12, "ry": 4},
        ],
    },
}


def _module_dir() -> Path:
    return Path(__file__).resolve().parent


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


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


def _zone_views(copy: dict[str, Any]) -> dict[str, Any]:
    views: list[dict[str, Any]] = []
    for zone in copy["face_map"]["zones"][:8]:
        status = zone.get("status", "attention")
        theme = STATUS_THEME.get(status, STATUS_THEME["attention"])
        layout = RAIL_LAYOUT.get(zone.get("shape", "forehead"), RAIL_LAYOUT["forehead"])
        views.append(
            {
                **zone,
                "status_name": theme["name"],
                "status_class": theme["class"],
                "stroke": theme["stroke"],
                "fill": theme["fill"],
                "rail": layout["rail"],
                "top": layout["top"],
                "anchor_x": layout["anchor"][0],
                "anchor_y": layout["anchor"][1],
                "line_x": layout["line"][0],
                "line_y": layout["line"][1],
                "shape": layout["shape"],
            }
        )
    left = [zone for zone in views if zone["rail"] == "left"]
    right = [zone for zone in views if zone["rail"] == "right"]
    return {"all": views, "left": left[:4], "right": right[:4]}


def _screenshot_html(html: str, output_path: Path) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is required for protocol_v4. Install playwright and Chromium.") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    executable_path = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
    if not executable_path:
        for candidate in ("/usr/bin/chromium", "/usr/bin/chromium-browser", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
            if Path(candidate).exists():
                executable_path = candidate
                break
    with sync_playwright() as playwright:
        kwargs: dict[str, Any] = {"args": ["--no-sandbox", "--disable-dev-shm-usage"]}
        if executable_path:
            kwargs["executable_path"] = executable_path
        browser = playwright.chromium.launch(**kwargs)
        page = browser.new_page(viewport={"width": CANVAS_WIDTH, "height": CANVAS_HEIGHT}, device_scale_factor=1)
        page.set_content(html, wait_until="networkidle")
        page.screenshot(path=str(output_path), full_page=False, type="png")
        browser.close()


def render_face_protocol_v4(
    analysis_request_id: str,
    user_name: str,
    user_photo_url_or_path: str,
    protocol_slide_copy: dict[str, Any],
    output_dir: str,
    created_at: datetime,
) -> list[str]:
    raise RuntimeError(LEGACY_RENDERER_ERROR)
    logger.warning("PROTOCOL_V4_RENDERER_ACTIVE")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    normalized = normalize_protocol_slide_copy(protocol_slide_copy)
    date_value = created_at.strftime("%d.%m.%Y") if hasattr(created_at, "strftime") else str(created_at)
    context = {
        "css": _css(),
        "copy": normalized,
        "zones": _zone_views(normalized),
        "legend": [STATUS_THEME["good"], STATUS_THEME["attention"], STATUS_THEME["priority"]],
        "user_name": user_name or "Гость",
        "date": date_value,
        "photo_src": _image_src(user_photo_url_or_path),
    }

    specs = [
        ("slide_1_face_scan.html", f"protocol_v4_{analysis_request_id}_slide_1.png"),
        ("slide_2_result.html", f"protocol_v4_{analysis_request_id}_slide_2.png"),
        ("slide_3_90_day_plan.html", f"protocol_v4_{analysis_request_id}_slide_3.png"),
    ]
    paths: list[str] = []
    env = _env()
    for template, filename in specs:
        path = output / filename
        html = env.get_template(template).render(**context)
        (output / filename.replace(".png", ".html")).write_text(html, encoding="utf-8")
        _screenshot_html(html, path)
        paths.append(str(path))
    logger.info("Generated protocol_v4 slides: %s", paths)
    return paths
