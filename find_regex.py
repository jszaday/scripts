
#!/usr/bin/python3
import argparse
import os
import re
import sys
from collections import deque
from pathlib import Path
from typing import Iterator, Optional

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None  # We'll handle this gracefully


# Ensure stdout isn't block-buffered (macOS friendliness)
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass


def iter_entries(root: Path,
                 follow_symlinks: bool = False,
                 include_hidden: bool = False) -> Iterator[os.DirEntry]:
    """
    Stack-based traversal using os.scandir().
    Yields os.DirEntry items reachable from 'root'.
    - Skips hidden files/dirs unless include_hidden=True
    - Does NOT follow symlinked directories unless follow_symlinks=True
    """
    stack = deque([root])

    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    # Hidden filter (don't treat the root itself as hidden)
                    if not include_hidden and entry.name.startswith('.') and current != root:
                        continue

                    yield entry

                    # If directory, push to stack
                    try:
                        if entry.is_dir(follow_symlinks=follow_symlinks):
                            # Avoid following symlinked dirs unless explicitly requested
                            if not follow_symlinks and entry.is_symlink():
                                continue
                            stack.append(Path(entry.path))
                    except OSError:
                        # Permission denied or other FS error; skip
                        continue
        except (PermissionError, FileNotFoundError, NotADirectoryError, OSError):
            # Skip directories we can't enter
            continue


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="find-regex",
        description="Find files (and optionally directories) under ROOT using os.scandir(), matching a regex pattern. Streams matches as they are found, with a tqdm progress bar."
    )
    p.add_argument("pattern", help="Regular expression to match (against basename by default)." )
    p.add_argument("--root", default=".", help="Root directory to start from (default: .)")
    p.add_argument("--fullpath", action="store_true",
                   help="Match the regex against the full path instead of just the basename.")
    p.add_argument("-i", "--ignore-case", action="store_true", help="Case-insensitive regex.")
    p.add_argument("--include-dirs", action="store_true", help="Include directories as matchable targets.")
    p.add_argument("--no-files", action="store_true", help="Exclude files; only consider directories as matchable targets.")
    p.add_argument("-L", "--follow-symlinks", action="store_true", help="Follow symlinked directories/files." )
    p.add_argument("-a", "--absolute", action="store_true", help="Output absolute paths.")
    p.add_argument("--hidden", action="store_true", help="Include hidden files and directories (names starting with '.').")
    p.add_argument("-o", "--output", type=str, default=None, help="Write results to this file instead of stdout.")
    p.add_argument("--no-progress", action="store_true", help="Disable tqdm progress bar.")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_argparser().parse_args(argv)

    include_files = not args.no_files

    root = Path(args.root)
    if not root.exists():
        print(f"Root path does not exist: {root}", file=sys.stderr)
        return 2

    flags = re.IGNORECASE if args.ignore_case else 0
    try:
        rx = re.compile(args.pattern, flags)
    except re.error as e:
        print(f"Invalid regex: {e}", file=sys.stderr)
        return 2

    # Progress setup (stderr so it doesn't contaminate stdout piping)
    use_tqdm = (not args.no_progress) and (tqdm is not None) and sys.stderr.isatty()
    pbar = tqdm(total=0, unit="entry", leave=False, dynamic_ncols=True, desc="Scanning") if use_tqdm else None

    # Output file handle if requested
    outfile = None
    if args.output:
        try:
            outfile = open(args.output, "w", encoding="utf-8", buffering=1)  # line-buffered
        except OSError as e:
            print(f"Failed to open output file: {e}", file=sys.stderr)
            return 1

    def emit(line: str) -> None:
        if outfile is not None:
            outfile.write(line + "\n")
        else:
            print(line, flush=True)

    try:
        for entry in iter_entries(root, follow_symlinks=args.follow_symlinks, include_hidden=args.hidden):
            if pbar is not None:
                pbar.update(1)

            # Determine type
            try:
                is_dir = entry.is_dir(follow_symlinks=args.follow_symlinks)
                is_file = entry.is_file(follow_symlinks=args.follow_symlinks)
            except OSError:
                continue

            # Skip if type not included
            if is_dir and not args.include_dirs:
                matchable = False
            elif is_file and not include_files:
                matchable = False
            else:
                matchable = True

            if not matchable:
                continue

            # Build match target (name vs full path)
            if args.fullpath:
                p = Path(entry.path)
                target = p.resolve().as_posix() if args.absolute else p.as_posix()
            else:
                target = entry.name

            try:
                if rx.search(target):
                    out_path = Path(entry.path).resolve() if args.absolute else Path(entry.path)
                    emit(out_path.as_posix())
            except re.error:
                # Shouldn't happen after compile, but be safe
                continue
    finally:
        if pbar is not None:
            pbar.close()
        if outfile is not None:
            try:
                outfile.close()
            except Exception:
                pass

    # If tqdm is missing and user wanted progress, warn gently
    if not args.no_progress and tqdm is None and sys.stderr.isatty():
        print("[note] tqdm not installed; run 'pip install tqdm' for a progress bar.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
