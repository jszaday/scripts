#!/usr/bin/env bash
set -euo pipefail

pattern="${1:-*}"

for f in $pattern; do
  [[ -f "$f" ]] || continue

  ext="${f##*.}"
  if [[ "$f" == "$ext" ]]; then
    ext=""
  else
    ext=".$ext"
  fi

  sha=$(shasum -a 256 "$f" | awk '{print $1}')
  newname="${sha}${ext}"

  if [[ -e "$newname" ]]; then
    echo "Skipping $f -> $newname (already exists)" >&2
    continue
  fi

  mv -v -- "$f" "$newname"
done
