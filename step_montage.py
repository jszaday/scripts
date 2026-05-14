#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import os
import re
from dataclasses import dataclass
from typing import List, Tuple, Optional

from PIL import Image, ImageDraw, ImageFont


STEP_RE = re.compile(r"(?:^|[/\\])step_(\d+)\.(png|jpg|jpeg|webp)$", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Square-crop + label step_*.png images and build a montage (Pillow)."
    )
    p.add_argument(
        "--glob",
        default="step_*.png",
        help="Input glob (default: step_*.png).",
    )
    p.add_argument(
        "--out",
        default="cover.png",
        help="Output montage path (default: cover.png).",
    )
    p.add_argument(
        "--xoff",
        type=int,
        default=0,
        help=(
            "X offset from center for the square crop in pixels "
            "(default: 0). Offset only matters when the crop is smaller "
            "than the image."
        ),
    )
    p.add_argument(
        "--yoff",
        type=int,
        default=-20,
        help=(
            "Y offset from center for the square crop in pixels "
            "(negative moves crop up) (default: -20). Offset only matters "
            "when the crop is smaller than the image."
        ),
    )
    p.add_argument(
        "--crop",
        type=int,
        default=0,
        help=(
            "Square crop size in pixels. 0 => auto (min dimension). "
            "Use this to crop a smaller square from a square image."
        ),
    )
    p.add_argument(
        "--tile",
        type=int,
        default=768,
        help="Output tile size (square) in pixels (default: 768).",
    )
    p.add_argument(
        "--pad",
        type=int,
        default=90,
        help="Bottom label band height in pixels (default: 90).",
    )
    p.add_argument(
        "--margin",
        type=int,
        default=0,
        help="Margin between tiles in pixels (default: 0).",
    )
    p.add_argument(
        "--cols",
        type=int,
        default=0,
        help="Number of columns for grid montage. 0 => single row (default: 0).",
    )

    # Label styling (BoW, monospaced, chunky)
    p.add_argument(
        "--font",
        default="",
        help="Path to a .ttf/.otf/.ttc font file. If empty, tries common macOS mono fonts then falls back.",
    )
    p.add_argument(
        "--fontsize",
        type=int,
        default=36,
        help="Font size in pixels (default: 36).",
    )
    p.add_argument(
        "--text",
        default="black",
        help="Text color (default: black).",
    )
    p.add_argument(
        "--bg",
        default="white",
        help="Background color for label band (default: white).",
    )
    p.add_argument(
        "--stroke",
        type=int,
        default=0,
        help="Optional stroke width for chunkier text (default: 0).",
    )
    p.add_argument(
        "--stroke_fill",
        default="white",
        help="Stroke color (default: white). Useful if you invert colors.",
    )
    p.add_argument(
        "--label_y",
        type=int,
        default=20,
        help="Vertical offset from bottom of band (pixels). Bigger => label rises (default: 20).",
    )
    return p.parse_args()


def find_images(pattern: str) -> List[str]:
    paths = glob.glob(pattern)
    paths = [p for p in paths if os.path.isfile(p)]
    # Sort lexicographically; works for step_000250 style
    paths.sort()
    return paths


def derive_label(path: str) -> str:
    m = STEP_RE.search(path)
    if m:
        # Trim leading zeros by int conversion
        step = int(m.group(1))
        return f"steps={step}"
    # Fallback: use stem
    stem = os.path.splitext(os.path.basename(path))[0]
    return stem


def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def square_crop_with_offset(
    img: Image.Image, xoff: int, yoff: int, crop_size: int
) -> Image.Image:
    w, h = img.size
    s = min(w, h)
    if crop_size > 0:
        s = min(s, crop_size)
    ox = (w - s) // 2 + xoff
    oy = (h - s) // 2 + yoff
    ox = clamp(ox, 0, w - s)
    oy = clamp(oy, 0, h - s)
    return img.crop((ox, oy, ox + s, oy + s))


def load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    # If user provided a font path, use it.
    if font_path:
        return ImageFont.truetype(font_path, size=size)

    # Reasonable macOS defaults (monospace).
    # Use first one that exists.
    candidates = [
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/SFNSMono.ttf",
        "/System/Library/Fonts/SFNSMono.ttf",
        "/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Courier New.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size=size)
            except Exception:
                pass

    # Fallback: PIL bitmap font (not pretty, but always available)
    return ImageFont.load_default()


def add_label_band(
    tile: Image.Image,
    label: str,
    pad: int,
    font: ImageFont.ImageFont,
    fg: str,
    bg: str,
    stroke: int,
    stroke_fill: str,
    label_y_from_bottom: int,
) -> Image.Image:
    w, h = tile.size
    out = Image.new("RGB", (w, h + pad), color=bg)
    out.paste(tile, (0, 0))

    draw = ImageDraw.Draw(out)

    # Center text within the band; nudge up by label_y_from_bottom
    # Use textbbox for accurate measurement
    bbox = draw.textbbox((0, 0), label, font=font, stroke_width=stroke)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    x = (w - tw) // 2
    y = h + (pad - th) // 2  # center in band
    # Apply "from bottom" offset: increase => rise (toward top of band)
    y = (h + pad) - th - label_y_from_bottom

    draw.text(
        (x, y),
        label,
        font=font,
        fill=fg,
        stroke_width=stroke,
        stroke_fill=stroke_fill,
    )
    return out


def resize_square(img: Image.Image, out_size: int) -> Image.Image:
    # Use high-quality resample for photos
    return img.resize((out_size, out_size), resample=Image.LANCZOS)


@dataclass
class Tile:
    img: Image.Image
    label: str
    path: str


def build_tiles(paths: List[str], args: argparse.Namespace) -> List[Tile]:
    font = load_font(args.font, args.fontsize)

    tiles: List[Tile] = []
    for p in paths:
        with Image.open(p) as im:
            im = im.convert("RGB")
            cropped = square_crop_with_offset(im, args.xoff, args.yoff, args.crop)
            resized = resize_square(cropped, args.tile)
            label = derive_label(p)
            labeled = add_label_band(
                resized,
                label=label,
                pad=args.pad,
                font=font,
                fg=args.text,
                bg=args.bg,
                stroke=args.stroke,
                stroke_fill=args.stroke_fill,
                label_y_from_bottom=args.label_y,
            )
            tiles.append(Tile(img=labeled, label=label, path=p))
    return tiles


def montage(tiles: List[Tile], cols: int, margin: int, bg: str) -> Image.Image:
    if not tiles:
        raise SystemExit("No input images matched.")

    tw, th = tiles[0].img.size
    for t in tiles:
        if t.img.size != (tw, th):
            raise SystemExit("Internal error: tile sizes differ.")

    n = len(tiles)
    if cols <= 0:
        cols = n
    rows = (n + cols - 1) // cols

    out_w = cols * tw + (cols - 1) * margin
    out_h = rows * th + (rows - 1) * margin
    out = Image.new("RGB", (out_w, out_h), color=bg)

    for i, t in enumerate(tiles):
        r = i // cols
        c = i % cols
        x = c * (tw + margin)
        y = r * (th + margin)
        out.paste(t.img, (x, y))

    return out


def main() -> None:
    args = parse_args()
    paths = find_images(args.glob)
    if not paths:
        raise SystemExit(f"No files matched glob: {args.glob}")

    tiles = build_tiles(paths, args)
    out = montage(tiles, cols=args.cols, margin=args.margin, bg=args.bg)
    out.save(args.out)
    print(f"Wrote {args.out} ({out.size[0]}x{out.size[1]}) from {len(paths)} images.")


if __name__ == "__main__":
    main()
