from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.reports.face_protocol_final.renderer import render_face_protocol_final_v1
from app.reports.face_protocol_final.schema import EXAMPLE_PROTOCOL_COPY


def main() -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = settings.storage_root() / "previews" / "face_protocol_final" / timestamp
    png_path = Path(
        render_face_protocol_final_v1(
            analysis_request_id="preview",
            user_name="АНАСТАСИЯ К.",
            user_photo_path_or_url="",
            protocol_copy=EXAMPLE_PROTOCOL_COPY,
            output_dir=str(output_dir),
            created_at=datetime.now(),
        )
    )
    generated_html = output_dir / "face_protocol_final_v1_preview.html"
    preview_html = output_dir / "preview.html"
    if generated_html.exists():
        shutil.copyfile(generated_html, preview_html)

    print(f"HTML preview: {preview_html.resolve()}")
    print(f"PNG preview: {png_path.resolve()}")


if __name__ == "__main__":
    main()
