from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw

from app.reports.protocol_v4.renderer import render_face_protocol_v4
from app.storage.local import local_storage


MOCK_PROTOCOL_SLIDE_COPY = {
    "face_map": {
        "title": "AI Face Scan",
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
        "skin_age": "Кожа выглядит свежей, с лёгкими признаками усталости.",
        "skin_type": "Комбинированная, склонная к отёчности.",
        "aging_type": "Усталый тип с акцентом на глаза и овал.",
        "strengths": "Выразительные глаза, хороший потенциал овала.",
    },
    "plan": {
        "causes": ["Отёчность в зоне глаз", "Напряжение межбровки", "Снижение тонуса овала"],
        "benefits": ["Более открытый взгляд", "Мягче носогубная зона", "Чётче нижний контур"],
        "forecast": ["меньше отёчности и свежее лицо", "мягче носогубная зона", "устойчивее овал и тонус"],
    },
}


def _create_test_photo(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (900, 1250), "#efe5dc")
    draw = ImageDraw.Draw(image)
    draw.ellipse((245, 130, 655, 625), fill="#d9b4a8", outline="#8d7770", width=4)
    draw.rectangle((365, 600, 535, 965), fill="#d9b4a8")
    draw.ellipse((320, 342, 405, 386), fill="#2f2926")
    draw.ellipse((495, 342, 580, 386), fill="#2f2926")
    draw.line((448, 390, 448, 515), fill="#8d7770", width=4)
    draw.arc((370, 392, 530, 560), 28, 152, fill="#8d7770", width=5)
    draw.line((386, 692, 514, 692), fill="#8d7770", width=6)
    draw.rectangle((0, 0, 900, 1250), outline="#eadbd1", width=22)
    image.save(path, quality=94)
    return str(path)


def main() -> None:
    print("USING_PROTOCOL_RENDERER=protocol_v4")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    preview_dir = Path(local_storage.abs_path(f"previews/protocol_v4/{timestamp}"))
    photo = _create_test_photo(preview_dir / "mock_photo.jpg")
    slides = render_face_protocol_v4(
        analysis_request_id="preview",
        user_name="test3",
        user_photo_url_or_path=photo,
        protocol_slide_copy=MOCK_PROTOCOL_SLIDE_COPY,
        output_dir=str(preview_dir),
        created_at=datetime.now(),
    )
    for slide in slides:
        print(str(Path(slide).resolve()))


if __name__ == "__main__":
    main()
