from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.reports.web_report_v6.renderer import render_bella_web_report_v6_template
from app.reports.web_report_v6.view_model import build_bella_web_report_v6_view_model


def _mock_protocol() -> dict:
    return {
        "protocol_version": "bella_face_protocol_v4",
        "client": {"name": "Preview", "age": 28, "date": "03.06.2026"},
        "skin_visual_age": {"passport_age": 28, "visual_age": 31, "text": "Кожа выглядит ухоженной, свежесть немного забирает зона глаз."},
        "skin_type": {"type_name": "Комбинированная, склонная к обезвоженности", "text": "Кожа ровная, но центральной зоне важно больше влаги."},
        "face_strengths": {
            "text": "У вас мягкая выразительная форма лица, аккуратный овал, красивые глаза и гармоничные пропорции.",
            "bullets": ["Форма лица — мягкая и выразительная", "Глаза — светлые и открытые", "Овал — аккуратный"],
        },
        "aging_type": {"type_id": "deformation_edema", "type_name": "Деформационно-отечный"},
        "face_fitness_benefits": {"bullets": ["Взгляд станет свежее", "Овал будет выглядеть собраннее"]},
        "zone_map": {
            "zones": [
                {"number": 1, "title": "Зона под глазами", "status": "yellow", "meaning": "Легкая отечность делает взгляд уставшим", "anchor": {"x": 50, "y": 40}},
                {"number": 2, "title": "Носогубная зона", "status": "yellow", "meaning": "Средняя треть просит поддержки", "anchor": {"x": 58, "y": 54}},
                {"number": 3, "title": "Овал лица / нижняя треть", "status": "orange", "meaning": "Овалу полезна регулярная поддержка", "anchor": {"x": 52, "y": 75}},
            ]
        },
    }


def build_preview() -> str:
    view_model = build_bella_web_report_v6_view_model(
        analysis_json={"bella_protocol_v4": _mock_protocol()},
        protocol_copy_json={"strict_blocks": _mock_protocol()},
        client={"name": "Preview", "age": 28, "analysis_date": "03 · 06 · 2026"},
        original_photo_url="",
        face_protocol_image_url="",
        settings=None,
    )
    return render_bella_web_report_v6_template(view_model, token="preview-token")


def main() -> None:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = Path("storage/previews/web_report_v6") / ts
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "preview.html"
    out_path.write_text(build_preview(), encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()
