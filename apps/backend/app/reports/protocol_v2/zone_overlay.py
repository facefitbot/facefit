from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from PIL import Image, ImageDraw, ImageFilter

from app.reports.protocol_v2.layout import PALETTE, font, measure_text


@dataclass(frozen=True)
class ZoneStyle:
    fill: tuple[int, int, int, int]
    outline: tuple[int, int, int, int]
    glow: tuple[int, int, int, int]


@dataclass(frozen=True)
class ZoneView:
    number: int
    key: str
    short_label: str
    status: str


ZONE_LABELS = {
    1: ("forehead", "Лоб"),
    2: ("glabella", "Межбровка"),
    3: ("eyes", "Глаза"),
    4: ("nasolabial", "Носогубка"),
    5: ("cheeks", "Скулы"),
    6: ("jawline", "Овал"),
    7: ("chin", "Подбородок"),
    8: ("neck", "Шея"),
    9: ("puffiness", "Отёчность"),
}

STATUS_STYLES = {
    "good": ZoneStyle((126, 164, 139, 28), (111, 149, 124, 185), (126, 164, 139, 54)),
    "attention": ZoneStyle((210, 175, 85, 30), (198, 157, 72, 185), (210, 175, 85, 54)),
    "priority": ZoneStyle((185, 108, 124, 32), (185, 108, 124, 190), (185, 108, 124, 58)),
}

STATUS_ALIASES = {
    "green": "good",
    "yellow": "attention",
    "red": "priority",
    "хорошо": "good",
    "внимание": "attention",
    "приоритет": "priority",
}


def _status(value: str | None, color: str | None = None) -> str:
    raw = (value or color or "attention").lower()
    if raw in STATUS_STYLES:
        return raw
    for key, status in STATUS_ALIASES.items():
        if key in raw:
            return status
    return "attention"


def _match_zone_number(zone: dict[str, Any]) -> int | None:
    number = zone.get("number")
    if isinstance(number, int) and number in ZONE_LABELS:
        return number
    name = str(zone.get("name") or "").lower()
    matches = {
        1: ("лоб", "forehead"),
        2: ("межбров", "glabella"),
        3: ("глаз", "веки", "eyes"),
        4: ("носогуб", "nasolabial"),
        5: ("скул", "cheek"),
        6: ("овал", "jaw"),
        7: ("подбород", "chin"),
        8: ("ше", "neck"),
        9: ("отеч", "отёч", "puff"),
    }
    for zone_number, keys in matches.items():
        if any(key in name for key in keys):
            return zone_number
    return None


def normalize_zones(analysis_json: dict[str, Any]) -> list[ZoneView]:
    by_number: dict[int, dict[str, Any]] = {}
    for zone in analysis_json.get("zones") or []:
        if not isinstance(zone, dict):
            continue
        matched = _match_zone_number(zone)
        if matched and matched not in by_number:
            by_number[matched] = zone

    result: list[ZoneView] = []
    for number in range(1, 10):
        key, label = ZONE_LABELS[number]
        source = by_number.get(number, {})
        result.append(
            ZoneView(
                number=number,
                key=key,
                short_label=label,
                status=_status(source.get("status"), source.get("color")),
            )
        )
    return result


def _rel(photo_box: tuple[int, int, int, int], x: float, y: float) -> tuple[int, int]:
    x0, y0, x1, y1 = photo_box
    return int(x0 + (x1 - x0) * x), int(y0 + (y1 - y0) * y)


def _rel_box(photo_box: tuple[int, int, int, int], box: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = photo_box
    return (
        int(x0 + (x1 - x0) * box[0]),
        int(y0 + (y1 - y0) * box[1]),
        int(x0 + (x1 - x0) * box[2]),
        int(y0 + (y1 - y0) * box[3]),
    )


def _draw_soft_shape(
    image: Image.Image,
    style: ZoneStyle,
    draw_shape: Callable[[ImageDraw.ImageDraw, tuple[int, int, int, int] | None], None],
) -> None:
    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    draw_shape(glow_draw, None)
    glow = glow.filter(ImageFilter.GaussianBlur(26))
    image.alpha_composite(glow)

    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    draw_shape(layer_draw, (4, 4, 4, 4))
    image.alpha_composite(layer)


def _ellipse_shape(image: Image.Image, photo_box: tuple[int, int, int, int], rel_box: tuple[float, float, float, float], style: ZoneStyle) -> None:
    box = _rel_box(photo_box, rel_box)

    def painter(draw: ImageDraw.ImageDraw, outline_width_marker: tuple[int, int, int, int] | None) -> None:
        if outline_width_marker is None:
            draw.ellipse(box, fill=style.glow)
        else:
            draw.ellipse(box, fill=style.fill, outline=style.outline, width=3)

    _draw_soft_shape(image, style, painter)


def _round_rect_shape(image: Image.Image, photo_box: tuple[int, int, int, int], rel_box: tuple[float, float, float, float], style: ZoneStyle, radius: int = 34) -> None:
    box = _rel_box(photo_box, rel_box)

    def painter(draw: ImageDraw.ImageDraw, outline_width_marker: tuple[int, int, int, int] | None) -> None:
        if outline_width_marker is None:
            draw.rounded_rectangle(box, radius=radius, fill=style.glow)
        else:
            draw.rounded_rectangle(box, radius=radius, fill=style.fill, outline=style.outline, width=3)

    _draw_soft_shape(image, style, painter)


def _polygon_shape(image: Image.Image, photo_box: tuple[int, int, int, int], points: list[tuple[float, float]], style: ZoneStyle) -> None:
    abs_points = [_rel(photo_box, x, y) for x, y in points]

    def painter(draw: ImageDraw.ImageDraw, outline_width_marker: tuple[int, int, int, int] | None) -> None:
        if outline_width_marker is None:
            draw.polygon(abs_points, fill=style.glow)
        else:
            draw.polygon(abs_points, fill=style.fill, outline=style.outline)
            draw.line(abs_points + [abs_points[0]], fill=style.outline, width=3, joint="curve")

    _draw_soft_shape(image, style, painter)


def _draw_zone_shape(image: Image.Image, photo_box: tuple[int, int, int, int], zone: ZoneView) -> None:
    style = STATUS_STYLES.get(zone.status, STATUS_STYLES["attention"])
    if zone.key == "forehead":
        _ellipse_shape(image, photo_box, (0.28, 0.035, 0.72, 0.22), style)
    elif zone.key == "glabella":
        _round_rect_shape(image, photo_box, (0.455, 0.185, 0.545, 0.36), style, radius=42)
    elif zone.key == "eyes":
        _ellipse_shape(image, photo_box, (0.185, 0.255, 0.435, 0.405), style)
        _ellipse_shape(image, photo_box, (0.565, 0.255, 0.815, 0.405), style)
    elif zone.key == "nasolabial":
        _round_rect_shape(image, photo_box, (0.355, 0.415, 0.435, 0.665), style, radius=38)
        _round_rect_shape(image, photo_box, (0.565, 0.415, 0.645, 0.665), style, radius=38)
    elif zone.key == "cheeks":
        _ellipse_shape(image, photo_box, (0.175, 0.405, 0.405, 0.61), style)
        _ellipse_shape(image, photo_box, (0.595, 0.405, 0.825, 0.61), style)
    elif zone.key == "jawline":
        _polygon_shape(image, photo_box, [(0.21, 0.62), (0.34, 0.78), (0.50, 0.83), (0.66, 0.78), (0.79, 0.62), (0.74, 0.72), (0.61, 0.87), (0.50, 0.91), (0.39, 0.87), (0.26, 0.72)], style)
    elif zone.key == "chin":
        _ellipse_shape(image, photo_box, (0.38, 0.74, 0.62, 0.87), style)
    elif zone.key == "neck":
        _polygon_shape(image, photo_box, [(0.36, 0.86), (0.64, 0.86), (0.70, 1.0), (0.30, 1.0)], style)
    elif zone.key == "puffiness":
        _ellipse_shape(image, photo_box, (0.20, 0.345, 0.42, 0.47), style)
        _ellipse_shape(image, photo_box, (0.58, 0.345, 0.80, 0.47), style)


LABEL_POSITIONS = {
    1: (0.40, 0.07),
    2: (0.55, 0.22),
    3: (0.06, 0.31),
    4: (0.63, 0.50),
    5: (0.05, 0.50),
    6: (0.72, 0.68),
    7: (0.39, 0.80),
    8: (0.57, 0.90),
    9: (0.06, 0.63),
}

ANCHORS = {
    1: (0.50, 0.13),
    2: (0.50, 0.27),
    3: (0.25, 0.35),
    4: (0.59, 0.54),
    5: (0.30, 0.52),
    6: (0.66, 0.72),
    7: (0.50, 0.80),
    8: (0.56, 0.92),
    9: (0.24, 0.42),
}


def _draw_zone_label(
    image: Image.Image,
    photo_box: tuple[int, int, int, int],
    label_bounds: tuple[int, int, int, int],
    zone: ZoneView,
) -> None:
    style = STATUS_STYLES.get(zone.status, STATUS_STYLES["attention"])
    draw = ImageDraw.Draw(image)
    anchor = _rel(photo_box, *ANCHORS[zone.number])
    x, y = _rel(label_bounds, *LABEL_POSITIONS[zone.number])

    label_font = font(25, bold=True)
    label = zone.short_label
    text_w, text_h = measure_text(draw, label, label_font)
    badge = 38
    padding_x = 16
    height = 44
    width = badge + text_w + padding_x * 2 + 8
    x0 = max(label_bounds[0] + 12, min(x, label_bounds[2] - width - 12))
    y0 = max(label_bounds[1] + 12, min(y, label_bounds[3] - height - 12))
    x1 = x0 + width
    y1 = y0 + height
    center = (x0 + badge // 2 + 6, y0 + height // 2)

    draw.line((anchor[0], anchor[1], center[0], center[1]), fill=(255, 253, 249, 210), width=3)
    draw.line((anchor[0], anchor[1], center[0], center[1]), fill=style.outline, width=2)
    draw.rounded_rectangle((x0, y0, x1, y1), radius=22, fill=(255, 253, 249, 240), outline=style.outline, width=1)
    draw.ellipse((x0 + 5, y0 + 5, x0 + 5 + badge, y0 + 5 + badge), fill=style.outline, outline=(255, 253, 249, 245), width=2)
    number_text = str(zone.number)
    number_font = font(21, bold=True)
    nw, nh = measure_text(draw, number_text, number_font)
    draw.text((x0 + 5 + (badge - nw) / 2, y0 + 5 + (badge - nh) / 2 - 1), number_text, font=number_font, fill="#FFFDF9")
    draw.text((x0 + badge + 18, y0 + (height - text_h) / 2 - 1), label, font=label_font, fill=PALETTE.text)


def draw_face_zones(
    image: Image.Image,
    photo_box: tuple[int, int, int, int],
    zones: list[ZoneView],
    *,
    label_bounds: tuple[int, int, int, int] | None = None,
) -> None:
    label_bounds = label_bounds or photo_box
    for zone in zones:
        _draw_zone_shape(image, photo_box, zone)
    for zone in zones:
        _draw_zone_label(image, photo_box, label_bounds, zone)
