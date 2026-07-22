#!/usr/bin/env python3
# rename_sequence.py — safely rename files to sequentially numbered names.
# Usage: ./rename_sequence.py 'frame_%04d.png' [--glob '*.png'] [--start N] [--sort-created] [--dry-run]

import argparse
import glob as glob_module
import os
import sys
import shutil
import platform
from pathlib import Path


def get_created_time(path: Path) -> float:
    if platform.system() == "Windows":
        return path.stat().st_ctime
    try:
        return path.stat().st_birthtime
    except AttributeError:
        return path.stat().st_mtime


def main():
    parser = argparse.ArgumentParser(
        description="Safely rename files using a printf-style pattern with an index placeholder."
    )
    parser.add_argument("pattern", help="Output pattern using %%d formatting (e.g., 'frame_%%04d.png')")
    parser.add_argument("--glob", default="*.png", help="Glob for input files (default: '*.png')")
    parser.add_argument("--start", type=int, default=1, help="Starting index (default: 1)")
    parser.add_argument("--sort-created", action="store_true", help="Sort files by creation time instead of name")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be renamed without making changes")
    args = parser.parse_args()

    files = glob_module.glob(args.glob)
    if not files:
        print(f"No files matched glob: {args.glob}")
        sys.exit(1)

    if args.sort_created:
        files = sorted(files, key=lambda f: get_created_time(Path(f)))
    else:
        files = sorted(files)

    # Validate pattern early
    try:
        _ = args.pattern % 1
    except Exception as e:
        print(f"Error: Invalid pattern '{args.pattern}'.")
        print(f"Make sure to include a type character like 'd' (e.g., 'img_%04d.png').")
        print(f"Details: {e}")
        sys.exit(1)

    renames = []
    target_names = set()
    for i, fname in enumerate(files, start=args.start):
        try:
            new_name = args.pattern % i
        except Exception as e:
            # This should generally be caught by the early validation, but keeping for safety.
            print(f"Error formatting pattern '{args.pattern}' with index {i}: {e}")
            sys.exit(1)

        if new_name in target_names:
            print(f"Error: duplicate target name: {new_name}")
            sys.exit(1)
        target_names.add(new_name)
        renames.append((fname, new_name))

    if args.dry_run:
        for src, dst in renames:
            print(f"[dry-run] {src} -> {dst}")
        return

    # Move through a temp dir to avoid collisions when source and target sets overlap.
    temp_dir = Path(".rename_sequence_tmp")
    if temp_dir.exists():
        print(f"Error: temp dir '{temp_dir}' already exists; remove it before proceeding.")
        sys.exit(1)
    temp_dir.mkdir()

    temp_map = {}
    for src, _ in renames:
        temp_path = temp_dir / Path(src).name
        shutil.move(src, temp_path)
        temp_map[src] = temp_path

    for src, dst in renames:
        shutil.move(temp_map[src], Path(dst))
        print(f"{src} -> {dst}")

    temp_dir.rmdir()
    print(f"Renamed {len(renames)} file(s).")


if __name__ == "__main__":
    main()
