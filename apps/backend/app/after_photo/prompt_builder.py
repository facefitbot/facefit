from __future__ import annotations

from app.after_photo.schemas import AfterPhotoIntensity, AfterPhotoPrompt, IntensityPreset
from app.core.config import settings

UNIVERSAL_AFTER_PHOTO_PROMPT = """Edit the provided portrait photo. This is a realistic face fitness transformation of the same exact person.

Preserve identity, age, skin tone, camera angle, lighting, background, expression, hair and all facial features.

Make the result visibly different from the original while still realistic:
- visibly lift the lower face and facial oval
- reduce lower-face heaviness by 30%
- reduce under-eye puffiness by 25%
- make jawline and cheekbones more defined
- make the face look less swollen, fresher and more toned
- slightly tighten the cheeks and nasolabial area
- keep real skin texture, pores, natural asymmetry and small imperfections

Important:
Do not return an image that looks almost identical to the input.
The before/after difference must be clearly noticeable, but not like surgery or beauty filter.

No makeup. No glossy skin. No plastic surgery. No over-smoothing.
Do not change eye shape, nose shape, lip shape, eyebrow shape, hairstyle, background or skin tone."""

UNIVERSAL_NEGATIVE_PROMPT = (
    "different person, changed identity, changed bone structure, plastic surgery, facelift surgery, "
    "fillers effect, doll skin, over-smoothed skin, glossy skin, fake beauty filter, heavy retouching, "
    "changed eye shape, changed nose, changed mouth, teenage look, heavy makeup, unrealistic skin, "
    "deformed face, distorted eyes, distorted teeth, asymmetry artifacts, blurry, low quality"
)

INTENSITY_PROMPT_ADDITIONS: dict[AfterPhotoIntensity, str] = {
    "subtle": "Apply very subtle natural improvements only.",
    "balanced": "Apply balanced natural improvements that are clearly visible but still realistic.",
    "visible": "Apply more visible but still believable natural improvements, while preserving identity and realism.",
}

EDIT_ATTEMPT_PROMPT_ADDITIONS: dict[int, str] = {
    1: (
        "Attempt 1: moderate realistic lift. Make the face clearly fresher and less puffy, "
        "with a natural lower-face lift that is visible in a before/after comparison."
    ),
    2: (
        "Attempt 2: stronger visible lift because the previous result was too subtle. "
        "Increase de-puffing, lower-face lift, cheek definition and jawline clarity while preserving identity."
    ),
    3: (
        "Attempt 3: strongest realistic lift while preserving identity. Make the improvement unmistakably visible: "
        "less swelling, tighter facial oval, more defined cheeks and jawline, still natural and not surgical."
    ),
}


def _normalize_intensity(intensity: str | None) -> AfterPhotoIntensity:
    value = (intensity or settings.after_photo_default_intensity or "balanced").strip().lower()
    if value in {"subtle", "balanced", "visible"}:
        return value  # type: ignore[return-value]
    return "balanced"


def get_intensity_preset(intensity: str | None) -> IntensityPreset:
    normalized = _normalize_intensity(intensity)
    strength = {
        "subtle": settings.after_photo_subtle_strength,
        "balanced": settings.after_photo_balanced_strength,
        "visible": settings.after_photo_visible_strength,
    }[normalized]
    return IntensityPreset(
        name=normalized,
        prompt_addition=INTENSITY_PROMPT_ADDITIONS[normalized],
        strength=strength,
        guidance=settings.after_photo_guidance,
    )


def stronger_intensity(intensity: str) -> AfterPhotoIntensity:
    current = _normalize_intensity(intensity)
    if current == "subtle":
        return "balanced"
    return "visible"


def conservative_intensity(intensity: str) -> AfterPhotoIntensity:
    current = _normalize_intensity(intensity)
    if current == "visible":
        return "balanced"
    return "subtle"


def build_after_photo_prompt(intensity: str, attempt_index: int = 1) -> dict:
    preset = get_intensity_preset(intensity)
    attempt = max(1, min(3, int(attempt_index or 1)))
    prompt = f"{UNIVERSAL_AFTER_PHOTO_PROMPT}\n\n{EDIT_ATTEMPT_PROMPT_ADDITIONS[attempt]}"
    return AfterPhotoPrompt(
        prompt=prompt,
        negative_prompt=UNIVERSAL_NEGATIVE_PROMPT,
        intensity=preset.name,
        preset=preset,
        attempt_index=attempt,
    ).model_dump()
