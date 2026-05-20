from __future__ import annotations

from datetime import datetime

from app.reports.protocol_v4.renderer import render_face_protocol_v4

EXPECTED_LEGACY_ERROR = "LEGACY_FACE_PROTOCOL_RENDERER_DISABLED_USE_FINAL_V1"


def main() -> None:
    try:
        render_face_protocol_v4("1", "Smoke", "missing.jpg", {}, "/tmp/protocol_v4", datetime.now())
    except RuntimeError as exc:
        if str(exc) != EXPECTED_LEGACY_ERROR:
            raise AssertionError(f"protocol_v4 returned wrong legacy error: {exc}") from exc
        print("protocol_v4 renderer disabled; use app.reports.face_protocol_final.smoke_test")
        return
    raise AssertionError("protocol_v4 renderer did not raise legacy renderer error")


if __name__ == "__main__":
    main()
