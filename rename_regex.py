#!/usr/bin/env python3
# rename_regex.py — batch rename files using regex substitution.
# Usage: ./rename_regex.py '*.png_original' r'^(.*\.png)_original$' r'\1'

import argparse
import glob
import os
import re
import sys

def main():
    parser = argparse.ArgumentParser(description="Batch rename files using regex substitution.")
    parser.add_argument("glob_pattern", help="Glob for files to rename, e.g. '*.png_original'")
    parser.add_argument("regex", help="Regex pattern to match in filenames, e.g. r'^(.*)\\.png_original$'")
    parser.add_argument("replacement", help="Replacement pattern, e.g. r'\\1.png'")
    parser.add_argument("-n", "--dry-run", action="store_true", help="Preview without renaming")
    args = parser.parse_args()

    files = sorted(glob.glob(args.glob_pattern))
    if not files:
        print("No files matched.")
        sys.exit(1)

    for path in files:
        dirname, basename = os.path.split(path)
        newname = re.sub(args.regex, args.replacement, basename)
        newpath = os.path.join(dirname, newname)

        if newpath == path:
            continue  # nothing to do

        if args.dry_run:
            print(f"{basename} -> {newname}")
        else:
            os.rename(path, newpath)
            print(f"Renamed: {basename} -> {newname}")

if __name__ == "__main__":
    main()
