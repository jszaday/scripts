#!/usr/bin/env bash
set -euo pipefail

# Requires: exiftool, ffmpeg
command -v exiftool >/dev/null 2>&1 || { echo "Error: exiftool not found"; exit 1; }
command -v ffmpeg >/dev/null 2>&1 || { echo "Error: ffmpeg not found"; exit 1; }

pattern="${1:-*}"

for f in $pattern; do
  [[ -f "$f" ]] || continue

  ext="${f##*.}"
  lower_ext="${ext,,}"  # lowercase for matching

  case "$lower_ext" in
    jpg|jpeg|png|gif|webp|tif|tiff|bmp|heic)
      echo "🖼 Stripping metadata (exiftool): $f"
      # exiftool creates a _original backup by default, so we remove it
      exiftool -overwrite_original -all= "$f" >/dev/null
      ;;
    mp4|mov|mkv|avi|mp3|m4a|wav|flac)
      echo "🎞 Stripping metadata (ffmpeg): $f"
      tmp="${f%.*}_stripped.${ext}"
      ffmpeg -i "$f" -map_metadata -1 -c copy "$tmp" -y >/dev/null 2>&1
      mv -v -- "$tmp" "$f"
      ;;
    *)
      echo "⚪ Skipping unsupported format: $f"
      ;;
  esac
done

echo "✅ Metadata stripping complete."
