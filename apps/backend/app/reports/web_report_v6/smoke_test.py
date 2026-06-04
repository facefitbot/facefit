from __future__ import annotations

import re

from app.reports.web_report_v6.canonical_zones import CANONICAL_ZONES
from app.reports.web_report_v6.preview import _mock_protocol
from app.reports.web_report_v6.renderer import WEB_REPORT_V6_VERSION, render_bella_web_report_v6_template
from app.reports.web_report_v6.view_model import EARLY_PERIODS, build_bella_web_report_v6_view_model, validate_web_report_quality


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    protocol = _mock_protocol()
    view = build_bella_web_report_v6_view_model(
        analysis_json={"bella_protocol_v4": protocol},
        protocol_copy_json={"strict_blocks": protocol},
        client={"name": "Smoke", "age": 28, "analysis_date": "03 · 06 · 2026"},
    )
    quality = validate_web_report_quality(view)

    _assert(view["report_version"] == WEB_REPORT_V6_VERSION, "wrong report_version")
    _assert(view["web_report_version"] == WEB_REPORT_V6_VERSION, "wrong web_report_version")
    zones = view["zone_map"]["zones"]
    _assert(zones, "zones empty")
    _assert(len({z["key"] for z in zones}) == len(zones), "duplicate zone keys")
    _assert(len({z["number"] for z in zones}) == len(zones), "duplicate zone numbers")
    _assert(all(z["key"] in CANONICAL_ZONES for z in zones), "unknown canonical zone")
    _assert("Источник: Telegram Bot" not in str(view), "old source label leaked")
    _assert("Замедление возрастных изменений" in str(view["benefits"]), "required benefit missing")
    _assert([item["period"] for item in view["early_changes"]["items"]] == list(EARLY_PERIODS), "wrong early periods")
    _assert(view["future"]["without_work"] and view["future"]["with_work"], "future scenarios missing")
    _assert(view["final_cta"]["button_text"], "final CTA missing")
    _assert(quality["passed"], f"quality failed: {quality}")

    html = render_bella_web_report_v6_template(view, token="smoke")
    removed_key = "after" + "_photo"
    _assert(removed_key not in view, "removed visualization key leaked into view model")
    _assert(removed_key not in html, "removed visualization leaked into HTML")
    _assert('class="chapter-nav"' in html, "mobile nav missing")
    _assert(not re.search(r"\bП\s+Р\s+И\s+О\s+Р", html), "spaced priority text found")
    print("web_report_v6 smoke passed")


if __name__ == "__main__":
    main()
