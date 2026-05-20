from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import replicate
from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageStat

from app.core.config import settings


def _improvement_weight() -> float:
    original_weight = max(0.0, min(1.0, settings.after_photo_original_weight))
    return max(0.0, min(1.0, 1.0 - original_weight))


def _mean_image_difference(original_path: str, generated_path: str) -> float:
    original = Image.open(original_path).convert("L").resize((128, 128), Image.Resampling.LANCZOS)
    generated = Image.open(generated_path).convert("L").resize((128, 128), Image.Resampling.LANCZOS)
    diff = ImageChops.difference(original, generated)
    return float(ImageStat.Stat(diff).mean[0])


def _is_identity_preserving_edit(input_path: str, generated_path: str) -> bool:
    try:
        original = Image.open(input_path)
        generated = Image.open(generated_path)
        if original.size != generated.size:
            return False
        return _mean_image_difference(input_path, generated_path) <= 22.0
    except Exception:
        return False


def generate_mock_after_photo(input_path: str, output_path: str) -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    image = Image.open(input_path).convert("RGB")
    image = ImageEnhance.Color(image).enhance(1.04)
    image = ImageEnhance.Brightness(image).enhance(1.03)
    image = ImageEnhance.Contrast(image).enhance(1.02)
    soft = image.filter(ImageFilter.SMOOTH_MORE)
    image = Image.blend(image, soft, _improvement_weight())
    image.save(output_path, quality=94)
    return output_path


def generate_after_photo(input_path: str, output_path: str, prompt: str, negative_prompt: str) -> str:
    if settings.ai_mock_mode or not (settings.replicate_api_token and settings.replicate_flux_model):
        return generate_mock_after_photo(input_path, output_path)

    client = replicate.Client(api_token=settings.replicate_api_token)
    with open(input_path, "rb") as image_file:
        request_input: dict[str, Any] = {
            "prompt": prompt,
            "input_image": image_file,
            "aspect_ratio": "match_input_image",
            "strength": settings.after_photo_strength,
            "guidance": settings.after_photo_guidance,
        }
        if negative_prompt:
            request_input["negative_prompt"] = negative_prompt
        try:
            result = client.run(settings.replicate_flux_model, input=request_input)
        except Exception as exc:
            message = str(exc)
            retried = False
            for key in ("negative_prompt", "strength", "guidance"):
                if key in request_input and key in message:
                    request_input.pop(key, None)
                    retried = True
            if not retried:
                raise
            image_file.seek(0)
            result = client.run(settings.replicate_flux_model, input=request_input)
    url = result[0] if isinstance(result, list) else str(result)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    raw_path = str(Path(output_path).with_name(f"{Path(output_path).stem}_raw{Path(output_path).suffix}"))
    if url.startswith("http"):
        with httpx.stream("GET", url, timeout=settings.after_photo_timeout_seconds) as response:
            response.raise_for_status()
            with open(raw_path, "wb") as file:
                for chunk in response.iter_bytes():
                    file.write(chunk)
        if _is_identity_preserving_edit(input_path, raw_path):
            Path(raw_path).replace(output_path)
        else:
            generate_mock_after_photo(input_path, output_path)
        Path(raw_path).unlink(missing_ok=True)
    return output_path
