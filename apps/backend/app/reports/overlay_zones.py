from __future__ import annotations

ZONE_COORDS = {
    "лоб": (0.50, 0.16),
    "межбров": (0.50, 0.30),
    "глаз": (0.50, 0.35),
    "веки": (0.50, 0.35),
    "носогуб": (0.50, 0.55),
    "скулы": (0.50, 0.46),
    "овал": (0.50, 0.72),
    "подбород": (0.50, 0.82),
    "шея": (0.50, 0.94),
    "отеч": (0.72, 0.40),
}

STATUS_COLORS = {
    "green": (113, 154, 126),
    "yellow": (214, 171, 77),
    "red": (196, 94, 91),
}


def zone_position(zone_name: str, image_box: tuple[int, int, int, int]) -> tuple[int, int]:
    x0, y0, x1, y1 = image_box
    lowered = zone_name.lower()
    rel_x, rel_y = 0.5, 0.5
    for key, coords in ZONE_COORDS.items():
        if key in lowered:
            rel_x, rel_y = coords
            break
    return int(x0 + (x1 - x0) * rel_x), int(y0 + (y1 - y0) * rel_y)

