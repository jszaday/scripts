#!/usr/bin/env bash
# generate-favicons.sh
# Usage: ./generate-favicons.sh input.png
# Generates favicon PNGs in the current directory using ImageMagick.

set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 input.png"
  exit 1
fi

INPUT="$1"

if [ ! -f "$INPUT" ]; then
  echo "Error: File '$INPUT' not found."
  exit 1
fi

declare -A sizes=(
  [16]=favicon-16x16.png
  [32]=favicon-32x32.png
  [48]=favicon-48x48.png
  [167]=favicon-167x167.png
  [180]=favicon-180x180.png
  [192]=favicon-192x192.png
)

for size in "${!sizes[@]}"; do
  output="${sizes[$size]}"
  echo "Generating $output..."
  convert "$INPUT" -resize "${size}x${size}" "$output"
done

echo "✅ All favicon files generated in $(pwd):"
for file in "${sizes[@]}"; do
  echo " - $file"
done
