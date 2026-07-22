#!/bin/zsh
# Uppercase file extensions in the current directory (non-recursive).
# Dry run by default; pass --commit to actually rename.

commit=0
[[ "$1" == "--commit" ]] && commit=1

typeset -A seen
for f in *.*; do
  ext="${f##*.}"
  base="${f%.*}"
  upper="${(U)ext}"

  [[ "$ext" == "$upper" ]] && continue

  target="${base}.${upper}"

  if [[ -n "${seen[$target]}" ]]; then
    echo "Skipping '$f': target '$target' already claimed by '${seen[$target]}' in this run"
    continue
  fi
  if [[ -e "$target" && "${target:l}" != "${f:l}" ]]; then
    echo "Skipping '$f': target '$target' already exists"
    continue
  fi
  seen[$target]="$f"

  if (( ! commit )); then
    echo "Would rename '$f' -> '$target'"
    continue
  fi

  tmp="${base}.__tmp__"
  mv -- "$f" "$tmp"
  mv -- "$tmp" "$target"
  echo "Renamed '$f' -> '$target'"
done

if (( ! commit )); then
  echo "\nDry run complete. Re-run with --commit to actually rename."
fi
