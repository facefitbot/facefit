from __future__ import annotations

from datetime import datetime

from app.reports.protocol_v2.renderer import generate_face_protocol_slides_v2

EXPECTED_LEGACY_ERROR = "LEGACY_FACE_PROTOCOL_RENDERER_DISABLED_USE_FINAL_V1"


def main() -> None:
    try:
        generate_face_protocol_slides_v2("1", "missing.jpg", {}, "Smoke", datetime.now(), "/tmp/protocol_v2")
    except RuntimeError as exc:
        if str(exc) != EXPECTED_LEGACY_ERROR:
            raise AssertionError(f"protocol_v2 returned wrong legacy error: {exc}") from exc
        print("protocol_v2 renderer disabled; use app.reports.face_protocol_final.smoke_test")
        return
    raise AssertionError("protocol_v2 renderer did not raise legacy renderer error")


if __name__ == "__main__":
    main()
