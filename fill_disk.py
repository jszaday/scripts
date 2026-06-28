#!/usr/bin/env python3
# fill_disk.py — fill free disk space in ~200 ticks, then release it.
# Usage: ./fill_disk.py [--output fill.bin] [--ticks 200] [--margin 64M] [--zeros]

import argparse
import errno
import os
import sys
import time
from pathlib import Path


def parse_size(s: str) -> int:
    suffixes = {"K": 1024, "M": 1024**2, "G": 1024**3}
    s = s.strip()
    if s and s[-1].upper() in suffixes:
        return int(s[:-1]) * suffixes[s[-1].upper()]
    return int(s)


def free_bytes(path: Path) -> int:
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize


def main():
    parser = argparse.ArgumentParser(
        description="Fill free disk space in fixed ticks, then delete the file."
    )
    parser.add_argument("--output", default="fill.bin", help="Scratch file to write (default: fill.bin)")
    parser.add_argument("--ticks", type=int, default=200, help="Number of write steps (default: 200)")
    parser.add_argument("--margin", default="64M", help="Free space to leave untouched (default: 64M)")
    parser.add_argument("--zeros", action="store_true", help="Write zeros instead of random data (faster)")
    parser.add_argument("--keep", action="store_true", help="Do not delete the file after filling")
    args = parser.parse_args()

    out = Path(args.output)
    margin = parse_size(args.margin)

    initial_free = free_bytes(out.parent if out.parent.exists() else Path("."))
    usable = max(initial_free - margin, 0)
    if usable == 0:
        print("Error: no usable free space (already within margin).", file=sys.stderr)
        sys.exit(1)

    chunk_size = max(usable // args.ticks, 512)
    print(f"Free: {initial_free / 1024**2:.1f} MB  usable: {usable / 1024**2:.1f} MB  "
          f"chunk: {chunk_size / 1024:.0f} KB  ticks: {args.ticks}")

    written = 0
    tick = 0
    t0 = time.monotonic()
    try:
        with open(out, "wb") as f:
            while tick < args.ticks:
                current_free = free_bytes(out.parent if out.parent.exists() else Path("."))
                available = current_free - margin
                if available <= 0:
                    print(f"\nTick {tick}: within margin, stopping.")
                    break

                to_write = min(chunk_size, available)
                data = b"\x00" * to_write if args.zeros else os.urandom(to_write)
                try:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
                except OSError as e:
                    if e.errno == errno.ENOSPC:
                        print(f"\nTick {tick}: ENOSPC — disk full.")
                        break
                    raise

                written += to_write
                tick += 1
                pct = tick / args.ticks * 100
                free_mb = current_free / 1024**2
                print(f"  [{pct:5.1f}%] tick {tick:3d}/{args.ticks}  "
                      f"+{to_write // 1024}KB  free {free_mb:.1f}MB", end="\r")

        elapsed = time.monotonic() - t0
        tps = tick / elapsed if elapsed > 0 else 0
        print(f"\nWrote {written / 1024**2:.1f} MB to {out} in {elapsed:.1f}s ({tps:.1f} ticks/s).")
    except KeyboardInterrupt:
        elapsed = time.monotonic() - t0
        tps = tick / elapsed if elapsed > 0 else 0
        print(f"\nInterrupted after {written / 1024**2:.1f} MB in {elapsed:.1f}s ({tps:.1f} ticks/s).")

    if args.keep:
        print(f"Keeping {out} (--keep).")
        return

    input("Press Enter to delete and release space...")
    size = out.stat().st_size if out.exists() else 0
    out.unlink(missing_ok=True)
    print(f"Deleted {out} ({size / 1024**2:.1f} MB freed).")


if __name__ == "__main__":
    main()
