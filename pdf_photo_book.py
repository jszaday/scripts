#!/usr/bin/env python3
"""
Extract images from a PDF, resample to target DPI, optionally bake the ICC
profile to Display P3 (standard gamma), then lay each image out centered on a
page with its original caption.

Intermediate files live in a temporary directory and are cleaned up on exit.

Requirements:
    brew install mupdf imagemagick exiftool
    pip install reportlab pillow

Usage:
    python3 pdf_photo_book.py input.pdf output.pdf [options]

Options:
    --dpi INT           Target DPI (default: 300)
    --page-size PRESET  letter | a4 | a3 (default: letter)
    --margin FLOAT      Page margin in inches (default: 0.65)
    --font NAME         Caption font name (default: Helvetica)
    --font-size INT     Caption font size in points (default: 10)
    --no-icc-bake       Keep original ICC profile instead of converting to
                        Display P3 standard gamma
    --icc PATH          Path to target ICC profile for baking
                        (default: system Display P3)
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A3, A4, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
)

PAGE_SIZES = {"letter": letter, "a4": A4, "a3": A3}

DEFAULT_ICC = "/System/Library/ColorSync/Profiles/Display P3.icc"


# ── PDF parsing ──────────────────────────────────────────────────────────────

def extract_images(pdf: Path, out_dir: Path) -> list[Path]:
    """Extract raw images from PDF via mutool, preserving embedded ICC."""
    subprocess.run(
        ["mutool", "extract", str(pdf)],
        cwd=out_dir, check=True, capture_output=True,
    )
    return sorted(out_dir.glob("image-*"))


def extract_captions(pdf: Path) -> list[str]:
    """Extract per-page text from PDF; one caption per image page."""
    result = subprocess.run(
        ["mutool", "draw", "-F", "txt", str(pdf)],
        capture_output=True, text=True, check=True,
    )
    captions = []
    for line in result.stdout.splitlines():
        line = line.strip()
        # skip mutool progress lines ("page /path/to/file N")
        if line and not line.startswith("page "):
            captions.append(line)
    return captions


def image_ppis(pdf: Path) -> list[tuple[int, int]]:
    """Return (x_ppi, y_ppi) for each image in the PDF via pdfimages -list."""
    result = subprocess.run(
        ["pdfimages", "-list", str(pdf)],
        capture_output=True, text=True, check=True,
    )
    ppis = []
    for line in result.stdout.splitlines():
        if not line or line.startswith("page") or line.startswith("---"):
            continue
        parts = line.split()
        if len(parts) >= 13:
            ppis.append((int(parts[11]), int(parts[12])))
    return ppis


# ── Image processing ─────────────────────────────────────────────────────────

def resample(src: Path, dst: Path, x_ppi: int, y_ppi: int, target_dpi: int):
    with PILImage.open(src) as im:
        pw, ph = im.size
    nw = round(pw * target_dpi / x_ppi)
    nh = round(ph * target_dpi / y_ppi)
    subprocess.run([
        "magick", str(src),
        "-filter", "Lanczos",
        "-resize", f"{nw}x{nh}!",
        "-units", "PixelsPerInch",
        "-density", str(target_dpi),
        str(dst),
    ], check=True, capture_output=True)


def bake_icc(src: Path, dst: Path, icc_profile: str):
    subprocess.run([
        "magick", str(src),
        "-profile", icc_profile,
        str(dst),
    ], check=True, capture_output=True)


# ── PDF layout ───────────────────────────────────────────────────────────────

def build_pdf(
    images: list[Path],
    captions: list[str],
    out_pdf: Path,
    page_size: tuple,
    margin: float,
    font: str,
    font_size: int,
):
    page_w, page_h = page_size
    margin_pt = margin * inch
    caption_gap = 0.15 * inch
    caption_h = (font_size + 4) / 72 * inch  # rough line height

    avail_w = page_w - 2 * margin_pt
    max_img_h = page_h - 2 * margin_pt - caption_h - caption_gap

    caption_style = ParagraphStyle(
        "caption",
        fontName=font,
        fontSize=font_size,
        leading=font_size + 4,
        textColor=HexColor("#333333"),
        alignment=TA_CENTER,
    )

    doc = SimpleDocTemplate(
        str(out_pdf),
        pagesize=page_size,
        leftMargin=margin_pt, rightMargin=margin_pt,
        topMargin=margin_pt, bottomMargin=margin_pt,
    )

    story = []
    for i, (img_path, caption) in enumerate(zip(images, captions)):
        with PILImage.open(img_path) as im:
            pw, ph = im.size

        scale = min(avail_w / pw, max_img_h / ph)
        draw_w = pw * scale
        draw_h = ph * scale

        # vertically center the block (image + gap + caption)
        block_h = draw_h + caption_gap + caption_h
        top_pad = (max_img_h + caption_h + caption_gap - block_h) / 2
        if top_pad > 0:
            story.append(Spacer(1, top_pad))

        img = Image(str(img_path), width=draw_w, height=draw_h)
        img.hAlign = "CENTER"
        story.append(img)
        story.append(Spacer(1, caption_gap))
        story.append(Paragraph(caption, caption_style))

        if i < len(images) - 1:
            story.append(PageBreak())

    doc.build(story)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--page-size", choices=PAGE_SIZES, default="letter")
    parser.add_argument("--margin", type=float, default=0.65)
    parser.add_argument("--font", default="Helvetica")
    parser.add_argument("--font-size", type=int, default=10)
    parser.add_argument("--no-icc-bake", action="store_true")
    parser.add_argument("--icc", default=DEFAULT_ICC)
    args = parser.parse_args()

    pdf = args.input.expanduser().resolve()
    if not pdf.exists():
        sys.exit(f"Input not found: {pdf}")

    with tempfile.TemporaryDirectory(prefix="pdf_photo_book_") as tmp:
        tmp = Path(tmp)
        raw_dir = tmp / "raw"
        resampled_dir = tmp / "resampled"
        raw_dir.mkdir()
        resampled_dir.mkdir()

        print("Extracting images...")
        raw_images = extract_images(pdf, raw_dir)
        if not raw_images:
            sys.exit("No images found in PDF.")

        print("Reading source PPIs...")
        ppis = image_ppis(pdf)
        if len(ppis) != len(raw_images):
            print(f"Warning: pdfimages reported {len(ppis)} images, mutool extracted "
                  f"{len(raw_images)}; using available PPI data.")
        # pad with zeros if short; resample() treats 0 as "unknown"
        ppis += [(0, 0)] * max(0, len(raw_images) - len(ppis))

        print(f"Resampling to {args.dpi} DPI...")
        resampled = []
        for raw, (xppi, yppi) in zip(raw_images, ppis):
            dst = resampled_dir / (raw.stem + ".tif")
            resample(raw, dst, xppi or args.dpi, yppi or args.dpi, args.dpi)
            resampled.append(dst)

        final_images = resampled
        if not args.no_icc_bake:
            icc_path = Path(args.icc)
            if not icc_path.exists():
                print(f"Warning: ICC profile not found at {icc_path}, skipping bake.")
            else:
                print(f"Baking ICC profile ({icc_path.name})...")
                baked_dir = tmp / "baked"
                baked_dir.mkdir()
                baked = []
                for img in resampled:
                    dst = baked_dir / img.name
                    bake_icc(img, dst, str(icc_path))
                    baked.append(dst)
                final_images = baked

        print("Extracting captions...")
        captions = extract_captions(pdf)
        if len(captions) < len(final_images):
            # pad with empty strings if some pages have no text
            captions += [""] * (len(final_images) - len(captions))

        print("Building PDF...")
        build_pdf(
            final_images,
            captions[:len(final_images)],
            args.output.expanduser(),
            PAGE_SIZES[args.page_size],
            args.margin,
            args.font,
            args.font_size,
        )

    print(f"Done → {args.output}")


if __name__ == "__main__":
    main()
