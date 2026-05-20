from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw

from app.reports.protocol_v3.renderer import render_face_protocol_v3
from app.storage.local import local_storage


MOCK_PROTOCOL_SLIDE_COPY = {
    "face_map": {
        "title": "Face Protocol",
        "subtitle": "визуальный AI-разбор",
        "main_focus": ["Глаза", "Носогубка", "Овал"],
        "zones": [
            {"number": 1, "label": "Лоб", "status": "good", "shape": "forehead"},
            {"number": 2, "label": "Межбровка", "status": "attention", "shape": "glabella"},
            {"number": 3, "label": "Глаза", "status": "priority", "shape": "eyes"},
            {"number": 4, "label": "Носогубка", "status": "attention", "shape": "nasolabial"},
            {"number": 5, "label": "Скулы", "status": "good", "shape": "cheeks"},
            {"number": 6, "label": "Овал", "status": "priority", "shape": "jawline"},
            {"number": 7, "label": "Подбородок", "status": "attention", "shape": "chin"},
            {"number": 8, "label": "Шея", "status": "attention", "shape": "neck"},
        ],
    },
    "summary": {
        "skin_age": "Кожа выглядит свежей, есть лёгкие признаки усталости.",
        "skin_type": "Комбинированная, склонная к отёчности.",
        "aging_type": "Усталый тип с акцентом на глаза и овал.",
        "strengths": "Выразительные глаза, хороший потенциал овала.",
    },
    "plan": {
        "causes": ["Отёчность в зоне глаз", "Напряжение межбровки", "Снижение тонуса овала"],
        "benefits": ["Более открытый взгляд", "Мягче носогубная зона", "Чётче нижний контур"],
        "forecast": ["7–14 дней: меньше отёчности", "4–6 недель: свежее лицо", "8–12 недель: устойчивее овал"],
    },
}


def _create_test_photo(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (900, 1200), "#ead9cf")
    draw = ImageDraw.Draw(image)
    draw.ellipse((250, 150, 650, 620), fill="#d7b0a5", outline="#9a8177", width=4)
    draw.rectangle((360, 610, 540, 930), fill="#d7b0a5")
    draw.ellipse((315, 345, 400, 390), fill="#2f2926")
    draw.ellipse((500, 345, 585, 390), fill="#2f2926")
    draw.arc((365, 395, 535, 565), 25, 155, fill="#8f6b64", width=5)
    draw.line((390, 690, 510, 690), fill="#8f6b64", width=6)
    draw.text((285, 1010), "mock preview photo", fill="#766b64")
    image.save(path, quality=94)
    return str(path)


def main() -> None:
    print("USING_PROTOCOL_RENDERER=protocol_v3")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    preview_dir = Path(local_storage.abs_path(f"previews/protocol_v3/{timestamp}"))
    photo_path = _create_test_photo(preview_dir / "mock_photo.jpg")
    slides = render_face_protocol_v3(
        analysis_request_id="preview",
        user_name="test2",
        user_photo_url_or_path=photo_path,
        protocol_slide_copy=MOCK_PROTOCOL_SLIDE_COPY,
        output_dir=str(preview_dir),
        created_at=datetime.now(),
    )
    for slide in slides:
        print(str(Path(slide).resolve()))


if __name__ == "__main__":
    main()
