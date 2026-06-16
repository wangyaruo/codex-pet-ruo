#!/usr/bin/env python3
"""Split the generated 2x2 preview sheet into transparent state assets."""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "assets" / "preview_sheet.png"
STATES_DIR = REPO_ROOT / "assets" / "states"
TRIMMED_DIR = REPO_ROOT / "assets" / "states-trimmed"

STATES = [
    ("idle", "待机：比耶站姿", (0, 0)),
    ("wave", "挥手：开心打招呼", (1, 0)),
    ("wait", "等待：拿相机思考", (0, 1)),
    ("work", "工作：坐下使用电脑", (1, 1)),
]


def color_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return math.sqrt(sum((a[index] - b[index]) ** 2 for index in range(3)))


def estimate_background(image: Image.Image) -> tuple[int, int, int]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    sample_points = [
        (10, 10),
        (width - 11, 10),
        (10, height - 11),
        (width - 11, height - 11),
        (width // 2, 10),
        (width // 2, height - 11),
    ]
    samples = [rgb.getpixel(point) for point in sample_points]
    return tuple(round(sum(pixel[index] for pixel in samples) / len(samples)) for index in range(3))


def normalize_transparent_rgb(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    data = bytearray(rgba.tobytes())
    for index in range(0, len(data), 4):
        if data[index + 3] == 0:
            data[index] = 0
            data[index + 1] = 0
            data[index + 2] = 0
    return Image.frombytes("RGBA", rgba.size, bytes(data))


def remove_background(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    bg = estimate_background(rgba)
    pixels = rgba.load()
    width, height = rgba.size
    green_key = bg[1] - max(bg[0], bg[2]) > 80

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]

            if green_key:
                green_dominance = min(g - r, g - b)
                if g > 135 and green_dominance > 78:
                    alpha = 0
                elif g > 110 and green_dominance > 38:
                    alpha = round(min(255, max(0, (78 - green_dominance) / 40 * 220)))
                else:
                    alpha = a
            else:
                brightness = (r + g + b) / 3
                distance = color_distance((r, g, b), bg)
                if brightness > 236 and distance < 34:
                    alpha = 0
                elif brightness > 224 and distance < 64:
                    alpha = round(min(255, max(0, (distance - 26) / 38 * 210)))
                else:
                    alpha = a

            pixels[x, y] = (r, g, b, alpha)

    return normalize_transparent_rgb(rgba)


def trim_alpha(image: Image.Image, padding: int = 30) -> Image.Image:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        return image

    left, top, right, bottom = bbox
    return image.crop(
        (
            max(0, left - padding),
            max(0, top - padding),
            min(image.width, right + padding),
            min(image.height, bottom + padding),
        )
    )


def fit_to_canvas(image: Image.Image, size: int = 512, margin: int = 24) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    max_size = size - margin * 2
    scale = min(max_size / image.width, max_size / image.height)
    resized = image.resize(
        (round(image.width * scale), round(image.height * scale)),
        Image.Resampling.LANCZOS,
    )
    x = (size - resized.width) // 2
    y = size - margin - resized.height
    canvas.alpha_composite(resized, (x, y))
    return normalize_transparent_rgb(canvas)


def make_checker(size: tuple[int, int], cell: int = 16) -> Image.Image:
    image = Image.new("RGBA", size, (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            fill = (236, 236, 236, 255) if (x // cell + y // cell) % 2 == 0 else (204, 204, 204, 255)
            draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=fill)
    return image


def make_contact_sheet() -> None:
    tile = 560
    label_height = 42
    sheet = Image.new("RGBA", (tile * 2, (tile + label_height) * 2), (255, 255, 255, 255))
    draw = ImageDraw.Draw(sheet)

    for index, (name, label, _position) in enumerate(STATES):
        col = index % 2
        row = index // 2
        x = col * tile
        y = row * (tile + label_height)
        checker = make_checker((tile, tile))
        state = Image.open(STATES_DIR / f"{name}.png").convert("RGBA")
        checker.alpha_composite(state, ((tile - state.width) // 2, (tile - state.height) // 2))
        sheet.alpha_composite(checker, (x, y))
        draw.text((x + 22, y + tile + 10), name, fill=(32, 32, 32, 255))

    sheet.convert("RGB").save(REPO_ROOT / "assets" / "state_preview_checker.jpg", quality=95)


def main() -> None:
    STATES_DIR.mkdir(parents=True, exist_ok=True)
    TRIMMED_DIR.mkdir(parents=True, exist_ok=True)

    sheet = Image.open(SOURCE).convert("RGBA")
    quadrant_w = sheet.width // 2
    quadrant_h = sheet.height // 2
    state_map = {}

    for name, label, (col, row) in STATES:
        left = col * quadrant_w
        top = row * quadrant_h
        right = sheet.width if col == 1 else (col + 1) * quadrant_w
        bottom = sheet.height if row == 1 else (row + 1) * quadrant_h

        crop = sheet.crop((left, top, right, bottom))
        transparent = remove_background(crop)
        trimmed = trim_alpha(transparent)
        final = fit_to_canvas(trimmed)

        trimmed.save(TRIMMED_DIR / f"{name}.png")
        final.save(STATES_DIR / f"{name}.png")
        state_map[name] = {
            "label": label,
            "file": f"states/{name}.png",
            "trimmedFile": f"states-trimmed/{name}.png",
        }

    (REPO_ROOT / "assets" / "state-map.json").write_text(
        json.dumps(state_map, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    make_contact_sheet()


if __name__ == "__main__":
    main()
