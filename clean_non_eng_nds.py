#!/usr/bin/env python3
"""Remove .nds files under a directory that aren't plain-ENG or ENG-US(A).

Keeps filenames containing bare "ENG" (no region suffix) or "ENG-USA"/"ENG-US".
Purges everything else, including other ENG region variants (ENG-UK, ENG-AUS,
ENG-LAT, ENG-NET, ...) and non-English files.

Dry run by default; pass --commit to actually move files to Trash (via `trash`, reversible).
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

KEEP_RE = re.compile(r"ENG(-USA?)?(?![A-Za-z-])")


def should_keep(name: str) -> bool:
    return bool(KEEP_RE.search(name))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Directory to scan recursively for .nds files")
    parser.add_argument("--commit", action="store_true", help="Actually trash the files (default: dry run)")
    args = parser.parse_args()

    root = args.root
    if not root.is_dir():
        sys.exit(f"Not a directory: {root}")

    targets = [p for p in root.rglob("*.nds") if not should_keep(p.name)]

    if not targets:
        print("No matching files found.")
        return

    target_set = set(targets)
    # Directories that would end up empty once the targeted files are gone
    # (i.e. every .nds/other entry they contain is either a target or already empty).
    emptied_dirs = []
    for d in sorted((p for p in root.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        remaining = [c for c in d.iterdir() if c not in target_set and c not in emptied_dirs]
        if not remaining:
            emptied_dirs.append(d)

    print(f"{'Would trash' if not args.commit else 'Trashing'} {len(targets)} file(s):\n")
    for p in sorted(targets):
        print(f"  {p}")

    if emptied_dirs:
        print(f"\n{'Would also trash' if not args.commit else 'Also trashing'} {len(emptied_dirs)} directory(ies) left empty:\n")
        for d in sorted(emptied_dirs):
            print(f"  {d}")

    if not args.commit:
        print(f"\nDry run complete. {len(targets)} file(s) and {len(emptied_dirs)} director(ies) would be trashed. Re-run with --commit to actually trash them.")
        return

    subprocess.run(["trash", *[str(p) for p in targets]], check=True)
    if emptied_dirs:
        # Trash deepest dirs first so a dir isn't referenced after its parent is gone.
        subprocess.run(["trash", *[str(d) for d in sorted(emptied_dirs, key=lambda p: len(p.parts), reverse=True)]], check=True)
    print(f"\nTrashed {len(targets)} file(s) and {len(emptied_dirs)} director(ies).")


if __name__ == "__main__":
    main()
