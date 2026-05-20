from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from app.reports.protocol_v2.text_utils import draw_fitted_text, measure_text

WIDTH = 1080
HEIGHT = 1350
CANVAS_SIZE = (WIDTH, HEIGHT)


@dataclass(frozen=True)
class Palette:
    background: str = "#F8F3ED"
    background_alt: str = "#F7F1EA"
    card: str = "#FFFDF9"
    text: str = "#2F2926"
    text_secondary: str = "#766B64"
    border: str = "#DCCFC4"
    dusty_rose: str = "#B96C7C"
    muted_rose: str = "#C98291"
    sage: str = "#7EA48B"
    sage_dark: str = "#668A74"
    sand: str = "#D2AF55"
    sand_soft: str = "#E5C985"
    espresso: str = "#312A26"
    white: str = "#FFFDF9"


PALETTE = Palette()

_FONT_CANDIDATES = {
    "sans": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ],
    "sans_bold": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ],
    "serif": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/Library/Fonts/Georgia.ttf",
    ],
    "serif_bold": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
        "/Library/Fonts/Georgia Bold.ttf",
    ],
}


def _pick_font(kind: str) -> Path:
    for candidate in _FONT_CANDIDATES[kind]:
        path = Path(candidate)
        if path.exists():
            return path
    return Path(_FONT_CANDIDATES["sans"][0])


FONT_SANS = _pick_font("sans")
FONT_SANS_BOLD = _pick_font("sans_bold")
FONT_SERIF = _pick_font("serif")
FONT_SERIF_BOLD = _pick_font("serif_bold")


def font(size: int, *, bold: bool = False, serif: bool = False) -> ImageFont.FreeTypeFont:
    if serif and bold:
        path = FONT_SERIF_BOLD
    elif serif:
        path = FONT_SERIF
    elif bold:
        path = FONT_SANS_BOLD
    else:
        path = FONT_SANS
    return ImageFont.truetype(str(path), size=size)


def font_path(*, bold: bool = False, serif: bool = False) -> Path:
    if serif and bold:
        return FONT_SERIF_BOLD
    if serif:
        return FONT_SERIF
    if bold:
        return FONT_SANS_BOLD
    return FONT_SANS


def _hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    value = hex_color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), alpha


def make_canvas(background_path: str | None = None) -> Image.Image:
    if background_path and Path(background_path).exists():
        base = Image.open(background_path).convert("RGB")
        base = ImageOps.fit(base, CANVAS_SIZE, method=Image.Resampling.LANCZOS)
        return base.convert("RGBA")

    canvas = Image.new("RGBA", CANVAS_SIZE, PALETTE.background)
    grain = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(grain)
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=(255, 253, 249, 18))
    draw.line((72, 1268, WIDTH - 72, 1268), fill=(214, 201, 189, 80), width=1)
    canvas.alpha_composite(grain)
    return canvas


def draw_soft_panel(
    image: Image.Image,
    box: tuple[int, int, int, int],
    *,
    radius: int = 36,
    fill: str = PALETTE.card,
    border: str | None = PALETTE.border,
    shadow: bool = True,
    shadow_alpha: int = 34,
) -> None:
    if shadow:
        shadow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)
        sx0, sy0, sx1, sy1 = box
        shadow_draw.rounded_rectangle((sx0, sy0 + 10, sx1, sy1 + 12), radius=radius, fill=(73, 54, 44, min(shadow_alpha, 22)))
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(22))
        image.alpha_composite(shadow_layer)

    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(box, radius=radius, fill=fill)
    if border:
        draw.rounded_rectangle(box, radius=radius, outline=border, width=2)


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    text_font: ImageFont.FreeTypeFont,
    fill: str = PALETTE.text,
) -> None:
    width, height = measure_text(draw, text, text_font)
    x0, y0, x1, y1 = box
    draw.text((x0 + (x1 - x0 - width) / 2, y0 + (y1 - y0 - height) / 2), text, font=text_font, fill=fill)


def draw_header(
    image: Image.Image,
    *,
    user_name: str,
    date_text: str,
    subtitle: str = "Face Protocol",
    badge: str = "визуальный AI-разбор",
) -> None:
    draw = ImageDraw.Draw(image)
    draw_centered_text(draw, (0, 34, WIDTH, 100), "Bella Vladi", font(58, serif=True), PALETTE.espresso)
    draw_centered_text(draw, (0, 94, WIDTH, 150), subtitle, font(48, serif=True), PALETTE.espresso)
    meta = f"{user_name or 'Гость'} · {date_text}"
    draw_centered_text(draw, (0, 150, WIDTH, 194), meta, font(30), PALETTE.text)
    badge_font = font(24, bold=True)
    badge_w, badge_h = measure_text(draw, badge, badge_font)
    bx0 = int((WIDTH - badge_w - 50) / 2)
    by0 = 196
    draw.rounded_rectangle((bx0, by0, bx0 + badge_w + 50, by0 + 46), radius=23, fill="#FFFDF9", outline="#D7CBC0", width=1)
    draw.text((bx0 + 25, by0 + 8), badge, font=badge_font, fill=PALETTE.text)


def draw_slide_title(image: Image.Image, title: str, subtitle: str, *, y: int = 68) -> None:
    draw = ImageDraw.Draw(image)
    draw_centered_text(draw, (56, y, WIDTH - 56, y + 72), title, font(58, serif=True), PALETTE.espresso)
    draw_centered_text(draw, (80, y + 72, WIDTH - 80, y + 118), subtitle, font(30), PALETTE.text_secondary)


def draw_status_legend(image: Image.Image, x: int, y: int) -> None:
    draw = ImageDraw.Draw(image)
    items = [
        ("Все хорошо", PALETTE.sage),
        ("Зона внимания", PALETTE.sand),
        ("Приоритет", PALETTE.muted_rose),
    ]
    current_x = x
    item_font = font(26)
    for label, color in items:
        draw.ellipse((current_x, y + 3, current_x + 28, y + 31), fill=color, outline=_hex_to_rgba(color, 120), width=2)
        draw.text((current_x + 42, y), label, font=item_font, fill=PALETTE.text)
        label_w, _ = measure_text(draw, label, item_font)
        current_x += label_w + 88


def draw_card_text(
    image: Image.Image,
    box: tuple[int, int, int, int],
    *,
    title: str,
    text: str,
    accent: str,
    title_size: int = 28,
    body_max_size: int = 34,
    body_min_size: int = 30,
    body_lines: int = 2,
) -> None:
    draw_soft_panel(image, box, radius=34)
    draw = ImageDraw.Draw(image)
    x0, y0, x1, y1 = box
    draw.rounded_rectangle((x0 + 26, y0 + 26, x0 + 74, y0 + 74), radius=18, fill=accent)
    draw.text((x0 + 92, y0 + 24), title, font=font(title_size, bold=True), fill=PALETTE.text)
    draw_fitted_text(
        draw,
        text,
        (x0 + 30, y0 + 92, x1 - 30, y1 - 26),
        font_path(),
        body_max_size,
        body_min_size,
        body_lines,
        fill=PALETTE.text,
    )


def draw_runtime_marker(image: Image.Image) -> None:
    marker = "PROTOCOL V2 ACTIVE"
    draw = ImageDraw.Draw(image)
    marker_font = font(24, bold=True)
    text_w, text_h = measure_text(draw, marker, marker_font)
    x1 = WIDTH - 36
    y1 = HEIGHT - 24
    x0 = x1 - text_w - 28
    y0 = y1 - text_h - 18
    draw.rounded_rectangle((x0, y0, x1, y1), radius=18, fill=(185, 108, 124, 232), outline=(255, 253, 249, 235), width=2)
    draw.text((x0 + 14, y0 + 8), marker, font=marker_font, fill="#FFFDF9")


def draw_section_block(
    image: Image.Image,
    box: tuple[int, int, int, int],
    *,
    title: str,
    bullets: list[str],
    accent: str,
    body_size: int = 30,
) -> None:
    draw_soft_panel(image, box, radius=34)
    draw = ImageDraw.Draw(image)
    x0, y0, x1, y1 = box
    draw.text((x0 + 32, y0 + 26), title, font=font(32, bold=True), fill=PALETTE.text)
    y = y0 + 78
    bullet_font = font(body_size)
    for bullet in bullets[:3]:
        draw.ellipse((x0 + 34, y + 11, x0 + 48, y + 25), fill=accent)
        draw_fitted_text(
            draw,
            bullet,
            (x0 + 66, y, x1 - 30, y + 44),
            font_path(),
            body_size,
            28,
            1,
            fill=PALETTE.text,
        )
        y += 48


def paste_photo_cover(
    image: Image.Image,
    photo_path: str,
    box: tuple[int, int, int, int],
    *,
    radius: int = 38,
) -> tuple[int, int, int, int]:
    photo = Image.open(photo_path).convert("RGB")
    photo = ImageOps.exif_transpose(photo)
    x0, y0, x1, y1 = box
    box_size = (x1 - x0, y1 - y0)
    contained = ImageOps.contain(photo, box_size, method=Image.Resampling.LANCZOS).convert("RGBA")

    mask = Image.new("L", box_size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, box_size[0], box_size[1]), radius=radius, fill=255)
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((x0, y0 + 12, x1, y1 + 18), radius=radius, fill=(69, 49, 39, 26))
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    image.alpha_composite(shadow)

    photo_stage = Image.new("RGBA", box_size, "#F5EEE7")
    image.paste(photo_stage, (x0, y0), mask)
    contained_x = x0 + (box_size[0] - contained.width) // 2
    contained_y = y0 + (box_size[1] - contained.height) // 2
    image.alpha_composite(contained, (contained_x, contained_y))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(box, radius=radius, outline="#D1BFAE", width=3)
    return (contained_x, contained_y, contained_x + contained.width, contained_y + contained.height)


def save_rgb(image: Image.Image, output_path: str | Path, *, quality: int = 96) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(path, quality=quality)
    return str(path)
