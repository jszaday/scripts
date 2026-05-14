#!/usr/bin/env bash
# fix_extensions.sh — rename image files to match their actual content type.
# Usage: ./fix_extensions.sh
# Inspects every file in the current directory and renames any whose extension
# doesn't match the MIME type detected by `file`.
set -euo pipefail

for file in *; do
    [[ -f "$file" ]] || continue
    [[ "$file" == "$(basename "$0")" ]] && continue

    mime_type=$(file --mime-type -b "$file")

    case "$mime_type" in
        image/jpeg)  correct_ext="jpg"  ;;
        image/png)   correct_ext="png"  ;;
        image/gif)   correct_ext="gif"  ;;
        image/webp)  correct_ext="webp" ;;
        image/heic|image/heif) correct_ext="heic" ;;
        *) continue ;;
    esac

    current_ext="${file##*.}"
    current_ext="${current_ext,,}"

    if [[ "$current_ext" != "$correct_ext" ]]; then
        base_name="${file%.*}"
        new_filename="${base_name}.${correct_ext}"

        if [[ -e "$new_filename" ]]; then
            echo "[SKIP] '$file' -> '$new_filename' (target exists)"
        else
            mv "$file" "$new_filename"
            echo "[FIXED] '$file' -> '$new_filename'"
        fi
    fi
done
