#!/usr/bin/env bash
set -euo pipefail

command -v shasum >/dev/null 2>&1 || { echo "Error: shasum not found"; exit 1; }

pattern="${1:-*}"
status=0

for f in $pattern; do
  [[ -f "$f" ]] || continue

  ext="${f##*.}"
  if [[ "$f" == "$ext" ]]; then
    ext=""
    name="$f"
  else
    ext=".$ext"
    name="${f%$ext}"
  fi

  actual_sha=$(shasum -a 256 "$f" | awk '{print $1}')

  if [[ "$name" != "$actual_sha" ]]; then
    echo "❌ FAIL: $f"
    echo "    expected: $actual_sha$ext"
    echo "    actual:   $name$ext"
    status=1
  else
    echo "✔ OK: $f"
  fi
done

exit $status
