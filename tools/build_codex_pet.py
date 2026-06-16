#!/usr/bin/env python3
"""Build a Codex-compatible custom pet package from the Ruo state PNGs."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw


COLUMNS = 8
ROWS = 9
CELL_WIDTH = 192
CELL_HEIGHT = 208
ATLAS_WIDTH = COLUMNS * CELL_WIDTH
ATLAS_HEIGHT = ROWS * CELL_HEIGHT


@dataclass(frozen=True)
class RowSpec:
    row: int
    state: str
    source: str
    frame_count: int
    flip: bool = False


ROWS_SPECS = [
    RowSpec(0, "idle", "idle", 6),
    RowSpec(1, "running-right", "idle", 8),
    RowSpec(2, "running-left", "idle", 8, flip=True),
    RowSpec(3, "waving", "wave", 4),
    RowSpec(4, "jumping", "idle", 5),
    RowSpec(5, "failed", "wait", 8),
    RowSpec(6, "waiting", "wait", 6),
    RowSpec(7, "running", "work", 6),
    RowSpec(8, "review", "work", 6),
]


ANIMATION = {
    "idle": [
        {"dy": 0, "scale": 1.0},
        {"dy": -2, "scale": 1.01},
        {"dy": -3, "scale": 1.015},
        {"dy": -1, "scale": 1.005},
        {"dy": 0, "scale": 1.0},
        {"dy": 1, "scale": 0.995},
    ],
    "running-right": [
        {"dx": -5, "dy": 0, "scale": 1.0},
        {"dx": -3, "dy": -3, "scale": 1.012},
        {"dx": -1, "dy": 0, "scale": 1.0},
        {"dx": 1, "dy": -2, "scale": 1.01},
        {"dx": 3, "dy": 0, "scale": 1.0},
        {"dx": 5, "dy": -3, "scale": 1.012},
        {"dx": 3, "dy": 0, "scale": 1.0},
        {"dx": 1, "dy": -1, "scale": 1.006},
    ],
    "running-left": [
        {"dx": 5, "dy": 0, "scale": 1.0},
        {"dx": 3, "dy": -3, "scale": 1.012},
        {"dx": 1, "dy": 0, "scale": 1.0},
        {"dx": -1, "dy": -2, "scale": 1.01},
        {"dx": -3, "dy": 0, "scale": 1.0},
        {"dx": -5, "dy": -3, "scale": 1.012},
        {"dx": -3, "dy": 0, "scale": 1.0},
        {"dx": -1, "dy": -1, "scale": 1.006},
    ],
    "waving": [
        {"dy": 0, "scale": 1.0, "rotate": 0},
        {"dy": -3, "scale": 1.015, "rotate": -2},
        {"dy": -2, "scale": 1.01, "rotate": 2},
        {"dy": 0, "scale": 1.0, "rotate": 0},
    ],
    "jumping": [
        {"dy": 4, "scale": 0.99},
        {"dy": -8, "scale": 1.0},
        {"dy": -18, "scale": 1.01},
        {"dy": -8, "scale": 1.0},
        {"dy": 2, "scale": 0.995},
    ],
    "failed": [
        {"dx": 0, "dy": 6, "scale": 0.985, "rotate": 0},
        {"dx": -2, "dy": 7, "scale": 0.982, "rotate": -1},
        {"dx": 2, "dy": 7, "scale": 0.982, "rotate": 1},
        {"dx": 0, "dy": 8, "scale": 0.98, "rotate": 0},
        {"dx": -1, "dy": 7, "scale": 0.982, "rotate": -1},
        {"dx": 1, "dy": 7, "scale": 0.982, "rotate": 1},
        {"dx": 0, "dy": 6, "scale": 0.985, "rotate": 0},
        {"dx": 0, "dy": 6, "scale": 0.985, "rotate": 0},
    ],
    "waiting": [
        {"dy": 0, "scale": 1.0},
        {"dy": -1, "scale": 1.004},
        {"dy": -2, "scale": 1.008},
        {"dy": -1, "scale": 1.004},
        {"dy": 0, "scale": 1.0},
        {"dy": 1, "scale": 0.998},
    ],
    "running": [
        {"dy": 0, "scale": 1.0},
        {"dy": -4, "scale": 1.012},
        {"dy": -2, "scale": 1.006},
        {"dy": -4, "scale": 1.012},
        {"dy": 0, "scale": 1.0},
        {"dy": 1, "scale": 0.996},
    ],
    "review": [
        {"dx": 0, "dy": 0, "scale": 1.0},
        {"dx": -1, "dy": -1, "scale": 1.004, "rotate": -1},
        {"dx": -2, "dy": -1, "scale": 1.006, "rotate": -1},
        {"dx": -1, "dy": 0, "scale": 1.004, "rotate": 0},
        {"dx": 1, "dy": -1, "scale": 1.004, "rotate": 1},
        {"dx": 0, "dy": 0, "scale": 1.0},
    ],
}


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        return (0, 0, image.width, image.height)
    return bbox


def normalize_transparent_rgb(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    data = bytearray(rgba.tobytes())
    for index in range(0, len(data), 4):
        if data[index + 3] == 0:
            data[index] = 0
            data[index + 1] = 0
            data[index + 2] = 0
    return Image.frombytes("RGBA", rgba.size, bytes(data))


def load_source(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    image = image.crop(alpha_bbox(image))
    return normalize_transparent_rgb(image)


def make_base_cell(source: Image.Image, flip: bool) -> Image.Image:
    image = source.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if flip else source
    max_width = CELL_WIDTH - 16
    max_height = CELL_HEIGHT - 12
    scale = min(max_width / image.width, max_height / image.height)
    image = image.resize(
        (round(image.width * scale), round(image.height * scale)),
        Image.Resampling.LANCZOS,
    )

    cell = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), (0, 0, 0, 0))
    x = (CELL_WIDTH - image.width) // 2
    y = CELL_HEIGHT - image.height - 4
    cell.alpha_composite(image, (x, y))
    return normalize_transparent_rgb(cell)


def transform_cell(cell: Image.Image, frame: dict[str, float]) -> Image.Image:
    bbox = alpha_bbox(cell)
    sprite = cell.crop(bbox)

    scale = frame.get("scale", 1.0)
    if scale != 1.0:
        sprite = sprite.resize(
            (max(1, round(sprite.width * scale)), max(1, round(sprite.height * scale))),
            Image.Resampling.LANCZOS,
        )

    rotate = frame.get("rotate", 0)
    if rotate:
        sprite = sprite.rotate(rotate, expand=True, resample=Image.Resampling.BICUBIC)

    out = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), (0, 0, 0, 0))
    center_x = (bbox[0] + bbox[2]) / 2
    bottom_y = bbox[3]
    x = round(center_x - sprite.width / 2 + frame.get("dx", 0))
    y = round(bottom_y - sprite.height + frame.get("dy", 0))
    x = min(max(x, 0), CELL_WIDTH - sprite.width)
    y = min(max(y, 0), CELL_HEIGHT - sprite.height)
    out.alpha_composite(sprite, (x, y))
    return normalize_transparent_rgb(out)


def make_contact_sheet(atlas: Image.Image, output: Path) -> None:
    scale = 2
    label_width = 150
    row_height = CELL_HEIGHT // scale
    sheet = Image.new("RGB", (label_width + ATLAS_WIDTH // scale, ROWS * row_height), "white")
    draw = ImageDraw.Draw(sheet)

    for spec in ROWS_SPECS:
        y = spec.row * row_height
        draw.text((8, y + 8), spec.state, fill=(30, 30, 30))
        row = atlas.crop((0, spec.row * CELL_HEIGHT, ATLAS_WIDTH, (spec.row + 1) * CELL_HEIGHT))
        row = row.resize((ATLAS_WIDTH // scale, row_height), Image.Resampling.LANCZOS)
        checker = Image.new("RGB", row.size, "white")
        checker_draw = ImageDraw.Draw(checker)
        cell = 8
        for cy in range(0, checker.height, cell):
            for cx in range(0, checker.width, cell):
                fill = (232, 232, 232) if (cx // cell + cy // cell) % 2 == 0 else (204, 204, 204)
                checker_draw.rectangle((cx, cy, cx + cell - 1, cy + cell - 1), fill=fill)
        checker.paste(row.convert("RGB"), mask=row.getchannel("A"))
        sheet.paste(checker, (label_width, y))

    sheet.save(output, quality=95)


def build(repo_root: Path, output_dir: Path) -> None:
    assets_dir = repo_root / "assets" / "states"
    output_dir.mkdir(parents=True, exist_ok=True)

    sources = {source.stem: load_source(source) for source in assets_dir.glob("*.png")}
    atlas = Image.new("RGBA", (ATLAS_WIDTH, ATLAS_HEIGHT), (0, 0, 0, 0))

    for spec in ROWS_SPECS:
        base = make_base_cell(sources[spec.source], spec.flip)
        for column, frame in enumerate(ANIMATION[spec.state]):
            cell = transform_cell(base, frame)
            atlas.alpha_composite(cell, (column * CELL_WIDTH, spec.row * CELL_HEIGHT))

    atlas = normalize_transparent_rgb(atlas)
    atlas.save(output_dir / "spritesheet.webp", format="WEBP", lossless=True, quality=100, method=6, exact=True)
    atlas.save(output_dir / "spritesheet.png")
    make_contact_sheet(atlas, output_dir / "contact-sheet.jpg")

    manifest = {
        "id": "codex-pet-ruo",
        "displayName": "Ruo Chibi Pet",
        "description": "由照片生成的 Q 版动漫风格本地自定义 Codex 桌宠。",
        "spritesheetPath": "spritesheet.webp",
    }
    (output_dir / "pet.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=Path(__file__).resolve().parents[1], type=Path)
    parser.add_argument("--output-dir", default=None, type=Path)
    args = parser.parse_args()

    repo_root = args.repo_root.expanduser().resolve()
    output_dir = args.output_dir or repo_root / "dist" / "codex-pet-ruo"
    build(repo_root, output_dir.expanduser().resolve())
    print(output_dir.expanduser().resolve())


if __name__ == "__main__":
    main()
