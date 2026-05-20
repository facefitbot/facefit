from __future__ import annotations

import logging
import random
import shutil
import base64
import mimetypes
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageChops, ImageStat

from app.after_photo.prompt_builder import build_after_photo_prompt
from app.after_photo.quality_check import run_after_photo_quality_check
from app.after_photo.schemas import AfterPhotoFinalResult, AfterPhotoQualityResult
from app.core.config import settings
from app.storage.local import local_storage

logger = logging.getLogger(__name__)

OPENAI_IMAGE_EDIT_ENDPOINT = "https://api.openai.com/v1/images/edits"
MIN_VISIBLE_IMAGE_DIFF = 6.0
MAX_EDIT_ATTEMPTS = 3


class AfterPhotoTooSubtleError(RuntimeError):
    pass


def _copy_as_png(source_path: str, target_path: str) -> str:
    Path(target_path).parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as image:
        image.convert("RGB").save(target_path, format="PNG", optimize=True)
    return target_path


def _debug_dir() -> Path:
    primary = Path("/debug")
    try:
        primary.mkdir(parents=True, exist_ok=True)
        return primary
    except Exception:
        fallback = Path(local_storage.abs_path("debug"))
        fallback.mkdir(parents=True, exist_ok=True)
        logger.warning("Could not write to /debug, using fallback debug dir: %s", fallback)
        return fallback


def _save_debug_png(source_path: str, filename: str) -> None:
    try:
        target = _debug_dir() / filename
        with Image.open(source_path) as image:
            image.convert("RGB").save(target, format="PNG", optimize=True)
        logger.info("Saved after-photo debug file: %s", target)
    except Exception:
        logger.warning("Failed to save after-photo debug file: %s", filename, exc_info=True)


def _output_rel(analysis_request_id: str, index: int, retry_pass: int = 0) -> str:
    suffix = f"retry_{retry_pass}_variant_{index}" if retry_pass else f"variant_{index}"
    return f"after_photos/{analysis_request_id}/after_photo_{analysis_request_id}_{suffix}.png"


def _final_rel(analysis_request_id: str) -> str:
    return f"after_photos/{analysis_request_id}/after_photo_{analysis_request_id}_final.png"


def _download_model_output(result: Any, output_abs: str) -> str:
    url = result[0] if isinstance(result, list) and result else str(result)
    Path(output_abs).parent.mkdir(parents=True, exist_ok=True)
    raw_path = str(Path(output_abs).with_suffix(".raw"))
    if not url.startswith("http"):
        raise RuntimeError("Replicate returned a non-URL result")
    with httpx.stream("GET", url, timeout=settings.after_photo_timeout_seconds) as response:
        response.raise_for_status()
        with open(raw_path, "wb") as file:
            for chunk in response.iter_bytes():
                file.write(chunk)
    _copy_as_png(raw_path, output_abs)
    Path(raw_path).unlink(missing_ok=True)
    return output_abs


def _image_difference_score(source_path: str, output_path: str) -> float:
    source = Image.open(source_path).convert("RGB").resize((192, 192), Image.Resampling.LANCZOS)
    output = Image.open(output_path).convert("RGB").resize((192, 192), Image.Resampling.LANCZOS)
    diff = ImageChops.difference(source, output).convert("L")
    return float(ImageStat.Stat(diff).mean[0])


def _image_dimensions(path: str) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def _log_generation_result(
    *,
    model: str,
    endpoint: str,
    request_id: str | None,
    source_path: str,
    output_path: str,
    b64_json_exists: bool,
) -> float:
    output = Path(output_path)
    original_width, original_height = _image_dimensions(source_path)
    width, height = _image_dimensions(output_path)
    diff = _image_difference_score(source_path, output_path)
    is_different = diff >= MIN_VISIBLE_IMAGE_DIFF
    buffers_identical = Path(source_path).read_bytes() == output.read_bytes()
    logger.info(
        (
            "AFTER_PHOTO_IMAGE_GENERATION endpoint=%s model=%s request_id=%s "
            "original_dimensions=%sx%s generated_dimensions=%sx%s output_bytes=%s "
            "b64_json_exists=%s buffers_identical=%s diff_score=%.2f is_different=%s"
        ),
        endpoint,
        model,
        request_id or "n/a",
        original_width,
        original_height,
        width,
        height,
        output.stat().st_size if output.exists() else 0,
        b64_json_exists,
        buffers_identical,
        diff,
        is_different,
    )
    return diff


def _assert_after_photo_is_different(source_path: str, output_path: str) -> None:
    diff = _image_difference_score(source_path, output_path)
    if diff < MIN_VISIBLE_IMAGE_DIFF:
        raise AfterPhotoTooSubtleError(
            f"After-photo image edit produced a nearly unchanged image; diff_score={diff:.2f}, min_required={MIN_VISIBLE_IMAGE_DIFF:.2f}"
        )


def _save_openai_image_response(payload: dict[str, Any], output_abs: str) -> str:
    data = payload.get("data") or []
    if not data:
        raise RuntimeError("OpenAI image edit returned no image data")
    first = data[0]
    Path(output_abs).parent.mkdir(parents=True, exist_ok=True)
    if first.get("b64_json"):
        Path(output_abs).write_bytes(base64.b64decode(first["b64_json"]))
        return output_abs
    if first.get("url"):
        return _download_model_output(first["url"], output_abs)
    raise RuntimeError("OpenAI image edit returned neither b64_json nor url")


def _generate_openai_variant(photo_path: str, output_abs: str, prompt_payload: dict[str, Any], seed: int) -> str:
    model = settings.openai_after_photo_image_model or settings.openai_protocol_image_model or "gpt-image-2"
    prompt = (
        f"{prompt_payload['prompt']}\n\n"
        f"Negative constraints: {prompt_payload.get('negative_prompt') or ''}\n\n"
        "Use the uploaded portrait as the source image. Do not return the original photo unchanged."
    )
    mime = mimetypes.guess_type(photo_path)[0] or "image/jpeg"
    data: dict[str, str] = {
        "model": model,
        "prompt": prompt,
        "n": "1",
        "size": settings.openai_after_photo_image_size,
        "quality": settings.openai_after_photo_image_quality,
        "input_fidelity": "high",
        "output_format": "png",
    }
    response: httpx.Response | None = None
    for unsupported_key in (None, "input_fidelity", "quality", "output_format", "size"):
        if unsupported_key:
            data.pop(unsupported_key, None)
        with open(photo_path, "rb") as image_file:
            response = httpx.post(
                OPENAI_IMAGE_EDIT_ENDPOINT,
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                data=data,
                files={"image": (Path(photo_path).name, image_file, mime)},
                timeout=settings.after_photo_timeout_seconds,
            )
        if response.status_code < 400:
            break
        message = response.text.lower()
        if unsupported_key == "size" or not any(key in message for key in ("input_fidelity", "quality", "output_format", "size")):
            break
    if response is None or response.status_code >= 400:
        detail = response.text[:1200] if response is not None else "empty response"
        request_id = None
        if response is not None:
            request_id = (
                response.headers.get("x-request-id")
                or response.headers.get("openai-request-id")
                or response.headers.get("request-id")
            )
        logger.error(
            "OpenAI image edit failed model=%s endpoint=%s request_id=%s detail=%s",
            model,
            "/v1/images/edits",
            request_id or "n/a",
            detail,
        )
        raise RuntimeError(f"OpenAI image edit failed with model={model}: {detail}")
    payload = response.json()
    first_item = (payload.get("data") or [{}])[0]
    b64_json_exists = bool(first_item.get("b64_json"))
    saved = _save_openai_image_response(payload, output_abs)
    request_id = (
        response.headers.get("x-request-id")
        or response.headers.get("openai-request-id")
        or response.headers.get("request-id")
    )
    _log_generation_result(
        model=model,
        endpoint="/v1/images/edits",
        request_id=request_id,
        source_path=photo_path,
        output_path=saved,
        b64_json_exists=b64_json_exists,
    )
    _assert_after_photo_is_different(photo_path, saved)
    return saved


def _generate_flux_variant(photo_path: str, output_abs: str, prompt_payload: dict[str, Any], seed: int) -> str:
    if settings.ai_mock_mode:
        return _copy_as_png(photo_path, output_abs)

    provider = (settings.after_photo_provider or "replicate").strip().lower()
    if provider == "openai":
        return _generate_openai_variant(photo_path, output_abs, prompt_payload, seed)

    import replicate

    client = replicate.Client(api_token=settings.replicate_api_token)
    preset = prompt_payload.get("preset") or {}
    with open(photo_path, "rb") as image_file:
        request_input: dict[str, Any] = {
            "prompt": prompt_payload["prompt"],
            "input_image": image_file,
            "aspect_ratio": "match_input_image",
            "strength": float(preset.get("strength") or settings.after_photo_strength),
            "guidance": float(preset.get("guidance") or settings.after_photo_guidance),
            "seed": seed,
        }
        if prompt_payload.get("negative_prompt"):
            request_input["negative_prompt"] = prompt_payload["negative_prompt"]
        try:
            result = client.run(settings.replicate_flux_model, input=request_input)
        except Exception as exc:
            message = str(exc)
            retried = False
            for key in ("negative_prompt", "strength", "guidance", "seed"):
                if key in request_input and key in message:
                    request_input.pop(key, None)
                    retried = True
            if not retried:
                raise
            image_file.seek(0)
            result = client.run(settings.replicate_flux_model, input=request_input)
    saved = _download_model_output(result, output_abs)
    _log_generation_result(
        model=settings.replicate_flux_model or "replicate",
        endpoint="replicate.run",
        request_id=None,
        source_path=photo_path,
        output_path=saved,
        b64_json_exists=False,
    )
    _assert_after_photo_is_different(photo_path, saved)
    return saved


def generate_after_photo_variants(
    analysis_request_id: str,
    photo_path: str,
    intensity: str | None = None,
    retry_pass: int = 0,
    attempt_index: int = 1,
    variant_count: int | None = None,
) -> list[str]:
    logger.info("AFTER_PHOTO_PIPELINE=universal_prompt_v1")
    prompt_payload = build_after_photo_prompt(intensity or settings.after_photo_default_intensity, attempt_index=attempt_index)
    logger.info("Selected intensity: %s", prompt_payload["intensity"])
    logger.info("Generating after-photo variants from source image: %s; edit_attempt=%s", photo_path, attempt_index)

    count = variant_count if variant_count is not None else (settings.after_photo_variant_count or settings.after_photo_variants or 3)
    variant_total = max(1, min(6, count))
    variant_paths: list[str] = []
    for index in range(1, variant_total + 1):
        output_rel = _output_rel(analysis_request_id, index, retry_pass)
        output_abs = local_storage.abs_path(output_rel)
        seed = random.randint(10_000, 999_999)
        _generate_flux_variant(photo_path, output_abs, prompt_payload, seed)
        if Path(output_abs).exists() and Path(output_abs).stat().st_size > 0:
            _assert_after_photo_is_different(photo_path, output_abs)
            if index == 1:
                _save_debug_png(output_abs, f"after-attempt-{attempt_index}.png")
            logger.info("Generated variant: %s", output_rel)
            variant_paths.append(output_rel)
        else:
            raise RuntimeError(f"After-photo variant was not created: {output_rel}")
    return variant_paths


def choose_best_after_photo_variant(qc_results: list[dict[str, Any]]) -> dict:
    results = [AfterPhotoQualityResult.model_validate(item) for item in qc_results]
    approved = [item for item in results if item.approved]
    if approved:
        best = max(approved, key=lambda item: item.ranking_score)
        return {"status": "approved", "variant_path": best.variant_path, "quality": best.model_dump(), "score": best.ranking_score}
    if not results:
        return {"status": "manual_review", "reason": "No quality results"}
    best = max(results, key=lambda item: item.ranking_score)
    return {"status": "manual_review", "variant_path": best.variant_path, "quality": best.model_dump(), "score": best.ranking_score}


def _quality_is_too_subtle(quality_results: list[dict[str, Any]]) -> bool:
    if not quality_results:
        return True
    parsed = [AfterPhotoQualityResult.model_validate(item) for item in quality_results]
    return all(not item.visible_improvement or item.recommendation == "retry" for item in parsed)


def generate_after_photo_final(
    analysis_request_id: str,
    original_photo_path: str,
    preferred_intensity: str | None = None,
) -> dict:
    intensity = (preferred_intensity or settings.after_photo_default_intensity or "balanced").strip().lower()
    if intensity not in {"subtle", "balanced", "visible"}:
        intensity = "balanced"

    provider = (settings.after_photo_provider or "replicate").strip().lower()
    if provider == "openai":
        has_generation_credentials = bool(settings.openai_api_key)
        missing_reason = "OPENAI_API_KEY is missing"
    else:
        has_generation_credentials = bool(settings.replicate_api_token and settings.replicate_flux_model)
        missing_reason = "REPLICATE_API_TOKEN or REPLICATE_FLUX_MODEL is missing"

    if not has_generation_credentials:
        logger.warning("No after-photo generation credentials, skipping after-photo generation")
        return AfterPhotoFinalResult(
            status="SKIPPED_NO_API_KEY",
            used_intensity=intensity,  # type: ignore[arg-type]
            reason=missing_reason,
        ).model_dump()

    all_variant_paths: list[str] = []
    all_quality_results: list[dict[str, Any]] = []
    used_retry = False
    retry_count = 0
    subtle_retry_reasons: list[str] = []

    try:
        _save_debug_png(original_photo_path, "original.png")
        for pass_index in range(MAX_EDIT_ATTEMPTS):
            retry_count = pass_index
            used_retry = pass_index > 0
            attempt_index = pass_index + 1
            current_intensity = ("balanced", "visible", "visible")[pass_index]
            logger.info("After-photo edit attempt %s/%s using intensity=%s", attempt_index, MAX_EDIT_ATTEMPTS, current_intensity)
            try:
                variant_rel_paths = generate_after_photo_variants(
                    analysis_request_id=analysis_request_id,
                    photo_path=original_photo_path,
                    intensity=current_intensity,
                    retry_pass=pass_index,
                    attempt_index=attempt_index,
                    variant_count=1,
                )
            except AfterPhotoTooSubtleError as exc:
                logger.warning("After-photo attempt %s too subtle, retrying stronger if available: %s", attempt_index, exc)
                subtle_retry_reasons.append(str(exc))
                if attempt_index < MAX_EDIT_ATTEMPTS:
                    continue
                raise
            all_variant_paths.extend(variant_rel_paths)
            variant_abs_paths = [local_storage.abs_path(path) for path in variant_rel_paths]
            qc = run_after_photo_quality_check(original_photo_path, variant_abs_paths)
            pass_results = qc.get("results", [])
            all_quality_results.extend(pass_results)
            best = choose_best_after_photo_variant(pass_results)
            if best.get("status") == "approved":
                final_rel = _final_rel(analysis_request_id)
                final_abs = local_storage.abs_path(final_rel)
                Path(final_abs).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(best["variant_path"], final_abs)
                logger.info("Approved final variant: %s", final_rel)
                return AfterPhotoFinalResult(
                    status="APPROVED",
                    final_path=final_rel,
                    variant_paths=all_variant_paths,
                    quality_results=[AfterPhotoQualityResult.model_validate(item) for item in all_quality_results],
                    used_intensity=current_intensity,  # type: ignore[arg-type]
                    used_retry=used_retry,
                    retry_count=retry_count,
                ).model_dump()

            if _quality_is_too_subtle(pass_results) and attempt_index < MAX_EDIT_ATTEMPTS:
                logger.warning("After-photo attempt %s was too subtle by quality check, retrying stronger", attempt_index)
                subtle_retry_reasons.extend(item.get("reason", "too subtle") for item in pass_results if isinstance(item, dict))
                continue

            if attempt_index < MAX_EDIT_ATTEMPTS:
                break

            if attempt_index >= MAX_EDIT_ATTEMPTS:
                break

        logger.warning("No approved after-photo variant, manual review required")
        return AfterPhotoFinalResult(
            status="NEEDS_MANUAL_REVIEW",
            final_path=None,
            variant_paths=all_variant_paths,
            quality_results=[AfterPhotoQualityResult.model_validate(item) for item in all_quality_results],
            used_intensity=intensity,  # type: ignore[arg-type]
            used_retry=used_retry,
            retry_count=retry_count,
            reason="; ".join(subtle_retry_reasons) or "No approved variant after quality check and retry",
        ).model_dump()
    except Exception as exc:
        logger.error("After-photo generation failed", exc_info=True)
        return AfterPhotoFinalResult(
            status="FAILED",
            final_path=None,
            variant_paths=all_variant_paths,
            quality_results=[AfterPhotoQualityResult.model_validate(item) for item in all_quality_results],
            used_intensity=intensity,  # type: ignore[arg-type]
            used_retry=used_retry,
            retry_count=retry_count,
            reason=str(exc),
        ).model_dump()
