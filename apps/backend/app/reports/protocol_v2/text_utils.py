from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

MIN_READABLE_FONT_SIZE = 22
_MEASURE_DRAW = ImageDraw.Draw(Image.new("RGB", (8, 8)))


@dataclass(frozen=True)
class FittedText:
    text: str
    lines: list[str]
    font: ImageFont.FreeTypeFont
    font_size: int
    bbox: tuple[int, int, int, int]
    overflow: bool = False


def _normalize_text(text: Any) -> str:
    value = "" if text is None else str(text)
    value = value.replace("\u00a0", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _line_bbox(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int, int, int]:
    if not text:
        return (0, 0, 0, 0)
    return draw.textbbox((0, 0), text, font=font)


def _line_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = _line_bbox(draw, text, font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def measure_text(
    draw: ImageDraw.ImageDraw,
    text: str | Iterable[str],
    font: ImageFont.ImageFont,
    max_width: int | None = None,
) -> tuple[int, int]:
    """Return real rendered width/height using textbbox.

    `max_width` is accepted for the renderer contract. The function never
    guesses by character count; wrapped text must be passed as multiple lines.
    """
    if isinstance(text, str):
        lines = text.splitlines() or [""]
    else:
        lines = list(text) or [""]
    widths: list[int] = []
    heights: list[int] = []
    for line in lines:
        width, height = _line_size(draw, line, font)
        widths.append(width)
        heights.append(height)
    line_gap = max(6, int(getattr(font, "size", 24) * 0.18))
    total_height = sum(heights) + max(0, len(lines) - 1) * line_gap
    width = max(widths) if widths else 0
    if max_width is not None:
        width = min(width, max_width)
    return width, total_height


def _split_long_word(word: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    pieces: list[str] = []
    current = ""
    for char in word:
        candidate = current + char
        if current and _line_size(_MEASURE_DRAW, candidate, font)[0] > max_width:
            pieces.append(current)
            current = char
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces or [word]


def _fits_width(text: str, font: ImageFont.ImageFont, max_width: int) -> bool:
    return _line_size(_MEASURE_DRAW, text, font)[0] <= max_width


def shorten_text_semantic(text: str, max_chars: int) -> str:
    """Shorten to a readable Russian phrase without visual ellipses."""
    cleaned = _normalize_text(text)
    if len(cleaned) <= max_chars:
        return cleaned

    lead_ins = [
        r"^визуально\s+",
        r"^по\s+визуальной\s+оценке\s+",
        r"^можно\s+отметить,\s+что\s+",
        r"^важно\s+отметить,\s+что\s+",
        r"^на\s+фото\s+видно,\s+что\s+",
        r"^в\s+целом\s+",
        r"^скорее\s+всего\s+",
    ]
    for pattern in lead_ins:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\b(очень|достаточно|выраженно|значительно|максимально)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;:-")

    parts = re.split(r"(?<=[.!?])\s+|;\s+|\s+—\s+|\s+-\s+", cleaned)
    if parts:
        first = parts[0].strip(" ,.;:-")
        if 0 < len(first) <= max_chars:
            return _finish_phrase(first)

    words = cleaned.split()
    result: list[str] = []
    for word in words:
        candidate = " ".join(result + [word])
        if len(candidate) > max_chars:
            break
        result.append(word)
    if not result and words:
        return words[0][:max_chars].strip(" ,.;:-")
    return _finish_phrase(" ".join(result).strip(" ,.;:-"))


def _finish_phrase(text: str) -> str:
    if not text:
        return ""
    if text[-1] in ".!?":
        return text
    return text + "."


def wrap_text(text: str, font: ImageFont.ImageFont, max_width: int, max_lines: int) -> list[str]:
    """Wrap by words with hard guarantees on width and line count."""
    cleaned = _normalize_text(text)
    if not cleaned:
        return [""]

    words: list[str] = []
    for word in cleaned.split(" "):
        if _fits_width(word, font, max_width):
            words.append(word)
        else:
            words.extend(_split_long_word(word, font, max_width))

    lines: list[str] = []
    current = ""
    index = 0
    while index < len(words):
        word = words[index]
        candidate = word if not current else f"{current} {word}"
        if _fits_width(candidate, font, max_width):
            current = candidate
            index += 1
            continue

        if current:
            lines.append(current)
            current = ""
            if len(lines) >= max_lines:
                break
        else:
            lines.append(word)
            index += 1
            if len(lines) >= max_lines:
                break

    if current and len(lines) < max_lines:
        lines.append(current)

    if len(lines) > max_lines:
        lines = lines[:max_lines]

    while lines and not _fits_width(lines[-1], font, max_width):
        lines[-1] = shorten_text_semantic(lines[-1], max(8, len(lines[-1]) - 4))

    return lines or [""]


def _load_font(font_path: str | Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(font_path), size=size)


def fit_text_to_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    font_path: str | Path,
    max_font_size: int,
    min_font_size: int,
    max_lines: int,
) -> FittedText:
    """Fit text into a rectangular box by measuring, wrapping and shortening."""
    x0, y0, x1, y1 = box
    max_width = max(1, x1 - x0)
    max_height = max(1, y1 - y0)
    min_size = max(MIN_READABLE_FONT_SIZE, min_font_size)
    text = _normalize_text(text)
    semantic_limit = max(24, min(len(text), max_lines * 46))

    candidates = [text]
    for ratio in (0.82, 0.68, 0.54, 0.42):
        shortened = shorten_text_semantic(text, max(18, int(semantic_limit * ratio)))
        if shortened and shortened not in candidates:
            candidates.append(shortened)

    fallback = shorten_text_semantic(text, 28) or "Ключевая зона."
    if fallback not in candidates:
        candidates.append(fallback)

    for candidate in candidates:
        for size in range(max_font_size, min_size - 1, -2):
            font = _load_font(font_path, size)
            lines = wrap_text(candidate, font, max_width, max_lines)
            width, height = measure_text(draw, lines, font, max_width)
            if width <= max_width and height <= max_height:
                return FittedText(
                    text=" ".join(lines),
                    lines=lines,
                    font=font,
                    font_size=size,
                    bbox=(x0, y0, x0 + width, y0 + height),
                    overflow=False,
                )

    font = _load_font(font_path, min_size)
    words = (fallback or "Коротко.").split()
    while words:
        candidate = " ".join(words)
        lines = wrap_text(candidate, font, max_width, max_lines)
        width, height = measure_text(draw, lines, font, max_width)
        if width <= max_width and height <= max_height:
            return FittedText(
                text=" ".join(lines),
                lines=lines,
                font=font,
                font_size=min_size,
                bbox=(x0, y0, x0 + width, y0 + height),
                overflow=False,
            )
        words = words[:-1]

    return FittedText(
        text="",
        lines=[""],
        font=font,
        font_size=min_size,
        bbox=(x0, y0, x0, y0),
        overflow=True,
    )


def draw_fitted_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    font_path: str | Path,
    max_font_size: int,
    min_font_size: int,
    max_lines: int,
    fill: str | tuple[int, int, int] = "#2F2926",
    line_spacing: int | None = None,
) -> FittedText:
    fitted = fit_text_to_box(draw, text, box, font_path, max_font_size, min_font_size, max_lines)
    x, y = box[0], box[1]
    spacing = line_spacing if line_spacing is not None else max(6, int(fitted.font_size * 0.2))
    for line in fitted.lines:
        draw.text((x, y), line, font=fitted.font, fill=fill)
        _, line_height = _line_size(draw, line, fitted.font)
        y += line_height + spacing
    return fitted


def assert_no_overflow(layout_elements: Iterable[dict[str, Any]]) -> bool:
    """Validate measured text bboxes against their assigned boxes."""
    ok = True
    for element in layout_elements:
        label = element.get("label", "text")
        box = element.get("box")
        bbox = element.get("bbox")
        if not box or not bbox:
            continue
        if bbox[0] < box[0] or bbox[1] < box[1] or bbox[2] > box[2] or bbox[3] > box[3]:
            ok = False
            logger.warning("Protocol v2 text overflow in %s: bbox=%s box=%s", label, bbox, box)
    return ok
