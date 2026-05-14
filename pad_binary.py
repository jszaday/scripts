#!/usr/bin/env python3
# pad_binary.py — zero-pad a binary file to a power of two or a specific size.
# Usage: ./pad_binary.py input.bin [-i] [--size 256K]

import argparse
import math
import os
import sys
from pathlib import Path


def parse_size(s: str) -> int:
    suffixes = {"K": 1024, "M": 1024**2, "G": 1024**3}
    s = s.strip()
    if s[-1].upper() in suffixes:
        return int(s[:-1]) * suffixes[s[-1].upper()]
    return int(s)


def next_power_of_two(n: int) -> int:
    if n <= 0:
        return 1
    return 1 << (n - 1).bit_length()


def main():
    parser = argparse.ArgumentParser(
        description="Zero-pad a binary file to a power of two or a specific size."
    )
    parser.add_argument("input", help="Input file")
    parser.add_argument("-i", "--in-place", action="store_true", help="Overwrite input file")
    parser.add_argument("--size", help="Target size (e.g. 256K, 1M, 262144). Default: next power of two.")
    args = parser.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(f"Error: '{src}' not found", file=sys.stderr)
        sys.exit(1)

    current_size = src.stat().st_size

    if args.size:
        target_size = parse_size(args.size)
    else:
        target_size = next_power_of_two(current_size)

    if target_size < current_size:
        print(f"Error: target size {target_size} is smaller than current size {current_size}", file=sys.stderr)
        sys.exit(1)

    if target_size == current_size:
        print(f"Already {current_size} bytes, nothing to do.")
        return

    if args.in_place:
        dst = src
    else:
        suffix = src.suffix
        stem = src.stem
        dst = src.with_name(f"{stem}_{target_size}{suffix}")

    data = src.read_bytes()
    padded = data + b"\x00" * (target_size - current_size)
    dst.write_bytes(padded)

    print(f"{src} ({current_size}B) -> {dst} ({target_size}B), padded {target_size - current_size}B")


if __name__ == "__main__":
    main()
