from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw

from app.reports.protocol_v2.renderer import generate_face_protocol_slides_v2
from app.storage.local import local_storage


MOCK_ANALYSIS_JSON = {
    "skin_visual_age": {
        "estimated_range": "визуально свежий диапазон",
        "explanation": "есть лёгкая усталость в зоне глаз и мягкая отёчность",
        "confidence": "medium",
    },
    "skin_type": {
        "type": "комбинированная",
        "features": ["ровный тон", "склонность к отёчности"],
        "strengths": ["хорошая плотность кожи"],
        "attention_points": ["зона глаз и овал лица"],
    },
    "face_type_and_aging_type": {
        "face_type": "мягкий овал",
        "aging_type": "усталый тип",
        "explanation": "акцент на отёчности, межбровке и нижнем контуре",
    },
    "zones": [
        {"number": 1, "name": "лоб", "status": "good", "color": "green"},
        {"number": 2, "name": "межбровная зона", "status": "attention", "color": "yellow"},
        {"number": 3, "name": "область глаз / веки", "status": "priority", "color": "red"},
        {"number": 4, "name": "носогубная зона", "status": "attention", "color": "yellow"},
        {"number": 5, "name": "скулы", "status": "good", "color": "green"},
        {"number": 6, "name": "овал лица", "status": "attention", "color": "yellow"},
        {"number": 7, "name": "подбородок", "status": "good", "color": "green"},
        {"number": 8, "name": "шея", "status": "good", "color": "green"},
        {"number": 9, "name": "зона отёчности", "status": "priority", "color": "red"},
    ],
    "causes": ["Отёчность в зоне глаз", "Напряжение межбровки", "Слабый тонус овала"],
    "strengths": ["Выразительные глаза", "хорошая плотность кожи"],
    "facefitness_benefits": ["Более открытый взгляд", "Мягче носогубная зона", "Чётче нижний контур"],
    "time_forecast": {
        "first_changes": "7–14 дней: меньше отёчности",
        "visible_changes": "4–6 недель: свежее лицо",
        "stable_result": "8–12 недель: устойчивее овал",
    },
    "summary": "Мягкий визуальный протокол с фокусом на глаза, отёчность и овал.",
    "cta_recommendation": "Получить персональную программу Bella Vladi",
}


def _create_test_photo(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (900, 1100), "#D8B8A9")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 900, 1100), fill="#CDA999")
    draw.ellipse((235, 120, 665, 805), fill="#E8C6B8", outline="#B8897D", width=5)
    draw.ellipse((315, 352, 390, 390), fill="#5F6E71")
    draw.ellipse((510, 352, 585, 390), fill="#5F6E71")
    draw.arc((370, 420, 530, 560), start=245, end=295, fill="#B8877A", width=5)
    draw.arc((365, 610, 535, 705), start=20, end=160, fill="#9F686F", width=6)
    draw.polygon([(292, 190), (608, 190), (700, 320), (625, 155), (450, 75), (280, 155)], fill="#4B3029")
    draw.rectangle((330, 770, 570, 1100), fill="#E3B9A8")
    image.save(path, quality=96)
    return str(path)


def main() -> None:
    print("USING_PROTOCOL_RENDERER=protocol_v2")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    preview_dir = Path(local_storage.abs_path(f"previews/protocol_v2/{timestamp}"))
    preview_dir.mkdir(parents=True, exist_ok=True)
    photo_path = _create_test_photo(preview_dir / "test_face.png")
    slide_paths = generate_face_protocol_slides_v2(
        analysis_request_id="preview",
        user_photo_path=photo_path,
        analysis_json=MOCK_ANALYSIS_JSON,
        user_name="Тест",
        created_at=datetime.now(),
        output_dir=str(preview_dir),
        single_image=False,
        use_ai_background=False,
        allow_mock_background=True,
    )
    for path in slide_paths:
        print(path)


if __name__ == "__main__":
    main()
