#!/bin/zsh
# concat_mp4s.zsh — concatenate all .mp4 files in the current directory
# Usage: ./concat_mp4s.zsh [output.mp4] [--reencode]

set -euo pipefail
emulate -L zsh
setopt null_glob

# ---- config / args ----
out="${1:-output.mp4}"
reencode="no"
[[ "${2:-}" == "--reencode" ]] && reencode="yes"

# ---- deps ----
command -v ffmpeg >/dev/null 2>&1 || {
  echo "ffmpeg not found. Install via: brew install ffmpeg" >&2
  exit 1
}

# ---- gather files (lexicographic) ----
typeset -a files
# zsh globs are already sorted lexicographically; null_glob avoids literal '*.mp4'
files=( *.mp4(.N) )

if (( ${#files} == 0 )); then
  echo "No .mp4 files found in the current directory." >&2
  exit 1
fi

# ---- create ffconcat list in CWD (not under /var) ----
listfile="$(mktemp -q ./ffconcat.XXXXXXXX.txt)"
trap 'rm -f -- "$listfile"' EXIT

# ---- write list with safe quoting for ffmpeg concat demuxer ----
# Need: file '<path-with-single-quotes-escaped-as-'"'"'>'
for f in "${files[@]}"; do
  # Escape any single quotes in the filename for inclusion inside single quotes
  esc="${f//\'/\047\\\047\047}"   # replace ' with '\'' (octal \047 for clarity)
  print -r -- "file '${esc}'" >> "$listfile"
done

# ---- run ffmpeg ----
if [[ "$reencode" == "yes" ]]; then
  # Re-encode to normalize parameters when inputs differ
  ffmpeg -hide_banner -loglevel warning \
    -f concat -safe 0 -i "$listfile" \
    -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p \
    -c:a aac -b:a 192k \
    "$out"
else
  # Stream copy: lossless & fast, requires matching codecs/params
  ffmpeg -hide_banner -loglevel warning \
    -f concat -safe 0 -i "$listfile" \
    -c copy \
    "$out" || {
      echo "Stream copy failed; try re-encoding: ./concat_mp4s.zsh \"$out\" --reencode" >&2
      exit 1
    }
fi

echo "✅ Combined video saved as: $out"
