#!/usr/bin/env python3
"""
img2png_seq.py

Read a text file containing a list of image paths (one per line),
convert each to PNG using ImageMagick, and write them sequentially
into an output directory as:

  000001.png, 000002.png, ...

Supports spaces in paths if the line is either:
- a raw path (no comments), or
- quoted (single/double)

Blank lines ignored. Lines starting with # ignored.
Inline comments supported via " # ..." (only if not inside quotes).

Requires: ImageMagick (`magick` on Windows/macOS/homebrew; `convert` on some Linux).
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List


def _strip_inline_comment(line: str) -> str:
    """
    Remove inline comments introduced by an unquoted '#'.
    """
    in_single = False
    in_double = False
    out = []
    for ch in line:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            break
        out.append(ch)
    return "".join(out).strip()


def read_paths(list_file: Path) -> List[Path]:
    paths: List[Path] = []
    with list_file.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            line = _strip_inline_comment(line)
            if not line:
                continue

            # Allow quoted paths; otherwise treat whole line as path.
            # If user wrote: "/path/with spaces.jpg"
            # shlex.split returns one token.
            try:
                tokens = shlex.split(line)
            except ValueError:
                # fallback: raw line
                tokens = [line]

            if len(tokens) != 1:
                raise ValueError(
                    f"Each non-empty line must resolve to exactly 1 path; got {tokens!r} from: {raw.rstrip()}"
                )
            paths.append(Path(tokens[0]).expanduser())
    return paths


def find_imagemagick_cmd(prefer: str | None) -> List[str]:
    """
    Returns the base command list to invoke ImageMagick.
    - prefer="magick" forces `magick`
    - prefer="convert" forces `convert`
    - prefer=None auto-detect
    """
    candidates = []
    if prefer:
        candidates.append(prefer)
    else:
        candidates.extend(["magick", "convert"])

    for exe in candidates:
        try:
            # 'magick -version' works; 'convert -version' works too
            subprocess.run(
                [exe, "-version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            return [exe]
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue

    raise RuntimeError(
        "ImageMagick not found. Install it and ensure `magick` or `convert` is on PATH.\n"
        "  macOS: brew install imagemagick\n"
        "  Ubuntu/Debian: sudo apt-get install imagemagick\n"
        "  Windows: https://imagemagick.org (ensure 'magick' is available)"
    )


def convert_one(
    base_cmd: List[str],
    src: Path,
    dst: Path,
    *,
    strip_metadata: bool,
    auto_orient: bool,
    overwrite: bool,
) -> None:
    if not src.exists():
        raise FileNotFoundError(f"Input not found: {src}")

    if dst.exists():
        if overwrite:
            dst.unlink()
        else:
            raise FileExistsError(f"Refusing to overwrite existing file: {dst}")

    # ImageMagick CLI:
    #   magick input -auto-orient -strip PNG32:output.png
    # For convert:
    #   convert input -auto-orient -strip PNG32:output.png
    cmd = base_cmd.copy()
    cmd.append(str(src))

    if auto_orient:
        cmd.append("-auto-orient")

    if strip_metadata:
        cmd.append("-strip")

    # Force PNG output; PNG32 is safe for alpha.
    cmd.append(f"PNG32:{dst}")

    subprocess.run(cmd, check=True)


def main(argv: List[str]) -> int:
    p = argparse.ArgumentParser(
        description="Convert a list of images to sequentially numbered PNGs using ImageMagick."
    )
    p.add_argument("list_file", type=Path, help="Text file containing image paths, one per line.")
    p.add_argument("out_dir", type=Path, help="Output directory to write PNGs into.")
    p.add_argument(
        "--start",
        type=int,
        default=1,
        help="Starting index for output filenames (default: 1).",
    )
    p.add_argument(
        "--digits",
        type=int,
        default=6,
        help="Zero-padding width for output filenames (default: 6 -> 000001.png).",
    )
    p.add_argument(
        "--tool",
        choices=["auto", "magick", "convert"],
        default="auto",
        help="Which ImageMagick entrypoint to use (default: auto).",
    )
    p.add_argument(
        "--strip-metadata",
        action="store_true",
        help="Strip metadata (EXIF, etc.) from outputs.",
    )
    p.add_argument(
        "--no-auto-orient",
        action="store_true",
        help="Disable auto-orient based on EXIF.",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting output files if they already exist.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be converted without running ImageMagick.",
    )

    args = p.parse_args(argv)

    paths = read_paths(args.list_file)
    if not paths:
        print("No input paths found in list file.", file=sys.stderr)
        return 2

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    tool_pref = None if args.tool == "auto" else args.tool
    base_cmd = find_imagemagick_cmd(tool_pref)

    auto_orient = not args.no_auto_orient

    idx = args.start
    failures = 0

    for src in paths:
        dst = out_dir / f"{idx:0{args.digits}d}.png"
        idx += 1

        if args.dry_run:
            print(f"{src} -> {dst}")
            continue

        try:
            convert_one(
                base_cmd,
                src,
                dst,
                strip_metadata=args.strip_metadata,
                auto_orient=auto_orient,
                overwrite=args.overwrite,
            )
        except Exception as e:
            failures += 1
            print(f"[FAIL] {src} -> {dst}: {e}", file=sys.stderr)

    if failures:
        print(f"Done with {failures} failure(s).", file=sys.stderr)
        return 1

    print(f"Done. Wrote {len(paths)} PNG(s) to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
