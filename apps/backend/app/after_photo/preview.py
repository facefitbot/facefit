from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil

from PIL import Image, ImageDraw

from app.after_photo.generator import generate_after_photo_final
from app.storage.local import local_storage


def _create_test_photo(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (768, 1024), "#e9d5c8")
    draw = ImageDraw.Draw(image)
    draw.ellipse((230, 180, 538, 560), fill="#d2a58f", outline="#8b6f61", width=4)
    draw.ellipse((305, 310, 335, 340), fill="#3b2c28")
    draw.ellipse((430, 310, 460, 340), fill="#3b2c28")
    draw.arc((315, 370, 455, 455), 20, 160, fill="#7a4e42", width=3)
    draw.arc((330, 430, 440, 510), 15, 165, fill="#8b3f3e", width=4)
    image.save(path, format="PNG")


def main() -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rel_dir = f"previews/after_photo/{timestamp}"
    abs_dir = Path(local_storage.abs_path(rel_dir))
    test_photo = abs_dir / "test_photo.png"
    _create_test_photo(test_photo)

    result = generate_after_photo_final(
        analysis_request_id=f"preview_{timestamp}",
        original_photo_path=str(test_photo),
        preferred_intensity=None,
    )
    copied_variants: list[Path] = []
    for index, rel_path in enumerate(result.get("variant_paths") or [], start=1):
        source = Path(local_storage.abs_path(rel_path))
        if source.exists():
            target = abs_dir / f"after_photo_preview_variant_{index}.png"
            shutil.copyfile(source, target)
            copied_variants.append(target)
    copied_final: Path | None = None
    if result.get("final_path"):
        source = Path(local_storage.abs_path(result["final_path"]))
        if source.exists():
            copied_final = abs_dir / "after_photo_preview_final.png"
            shutil.copyfile(source, copied_final)

    print("After-photo preview directory:", abs_dir.resolve())
    print("Status:", result.get("status"))
    for path in copied_variants:
        print("Variant:", path.resolve())
    if copied_final:
        print("Final:", copied_final.resolve())
    if result.get("status") == "SKIPPED_NO_API_KEY":
        print("Mock mode / skipped: Replicate API token or model is missing.")
    print("QC summary:", result.get("quality_results") or [])


if __name__ == "__main__":
    main()
