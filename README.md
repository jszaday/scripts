# scripts

A collection of utility scripts for file management, image/video processing, and system tasks.

Released under the [MIT License](LICENSE).

## Dependencies

| Tool | Install |
|------|---------|
| [ffmpeg](https://ffmpeg.org) | `brew install ffmpeg` |
| [ImageMagick](https://imagemagick.org) | `brew install imagemagick` |
| [exiftool](https://exiftool.org) | `brew install exiftool` |
| Python 3 | `brew install python` |
| Pillow | `pip install pillow` |
| OpenCV | `pip install opencv-python` |
| PyPDF2 | `pip install pypdf2` |
| tqdm | `pip install tqdm` |
| moviepy | `pip install moviepy` |
| wand | `pip install wand` |

---

## File management

### `rename_to_sha256.sh`
Rename files to their SHA-256 hash, preserving the original extension.
```
./rename_to_sha256.sh [glob]       # default glob: *
```

### `validate_sha256_filenames.sh`
Verify that each file's name matches its SHA-256 hash. Exits non-zero on any mismatch.
```
./validate_sha256_filenames.sh [glob]
```

### `fix_extensions.sh`
Detect the true MIME type of every file in the current directory and rename any whose extension doesn't match.
```
./fix_extensions.sh
```

### `pad.sh`
Pad purely numeric filenames to four digits (e.g., `7.jpg` → `0007.jpg`).
```
./pad.sh
```

### `rename_sequence.py`
Rename files to sequentially numbered names using a printf-style pattern. Renames via a temp directory to avoid collisions.
```
./rename_sequence.py 'frame_%04d.png' [--glob '*.jpg'] [--start 0] [--sort-created] [--dry-run]
```

### `rename_regex.py`
Batch rename files using a regex find-and-replace on their basenames.
```
./rename_regex.py '*.png_original' '^(.*\.png)_original$' '\1' [--dry-run]
```

### `find_regex.py`
Find files (and optionally directories) whose names match a regex, streaming results as they are found.
```
./find_regex.py PATTERN [--root DIR] [--fullpath] [-i] [--include-dirs] [-a] [--hidden]
```

---

## Image processing

### `strip_metadata.sh`
Strip all metadata from image files (via exiftool) and video/audio files (via ffmpeg). Overwrites files in place.
```
./strip_metadata.sh [glob]         # default: * (all files in cwd)
```

### `fix_extensions.sh`
*(Listed above under File management.)*

### `image_stats.sh`
Print a Markdown table of filename, width, height, and aspect ratio for all images in a directory.
```
./image_stats.sh [directory]       # default: current directory
```

### `normalize_tone.py`
Normalize color tone across JPEG images in the current directory using Reinhard color transfer in LAB space.
```
./normalize_tone.py [--preset neutral|warm|cool] [--ref reference.jpg] [--strength 0..1] [--outdir normalized]
```

### `shepards_distort.py`
Apply randomized Shepard's warp distortion to an image — a liquify-style warp from the command line.
```
./shepards_distort.py input.png output.png [--points 10] [--magnitude 2] [--angle 45] [--power 4.0]
```

### `tile_images.py`
Tile images in a brick pattern across a large canvas, optionally rotate the whole canvas, then center-crop to the target size.
```
./tile_images.py img1.png img2.png --width 1920 --height 1080 [--angle 45] [--scale 1.5] [--output out.png]
```

### `generate_favicons.sh`
Generate favicon PNGs at standard sizes (16, 32, 48, 167, 180, 192 px) from a source image using ImageMagick.
```
./generate_favicons.sh input.png
```

---

## Video processing

### `sync_loops.py`
Combine a looping audio file and a looping video file into a single output. Repeats each clip to reach a minimum length and adds optional audio fade in/out.
```
./sync_loops.py audio.mp3 video.mp4 output.mp4 [--min-length 30] [--fadeout 0.7] [--fadein 0.0]
```

### `concat_mp4.sh`
Concatenate all `.mp4` files in the current directory in lexicographic order.
```
./concat_mp4.sh [output.mp4] [--reencode]
```
`--reencode` re-encodes to h264/aac when input files have mismatched codecs or parameters.

---

## PDF

### `merge_pdfs.py`
Concatenate multiple PDFs into a single output file.
```
./merge_pdfs.py output.pdf input1.pdf input2.pdf [...]
```

---

## Image sequences

### `img2png_seq.py`
Convert a list of images to sequentially numbered PNGs using ImageMagick. Input is a text file with one path per line.
```
./img2png_seq.py list.txt out_dir/ [--start 1] [--digits 6] [--strip-metadata] [--dry-run]
```

### `step_montage.py`
Crop, label, and arrange `step_*.png` images into a grid montage. Useful for comparing generative model outputs across training steps.
```
./step_montage.py [--glob 'step_*.png'] [--out cover.png] [--tile 768] [--cols 4]
```

---

## System

### `provision_ovpn.sh`
Fully provision an OpenVPN server on a fresh Debian/Ubuntu machine, including PKI setup, server config, UFW rules, and a client `.ovpn` profile. Must be run as root.
```
sudo CLIENT_NAME=mydevice ./provision_ovpn.sh
```
Key environment variables: `CLIENT_NAME`, `VPN_NET`, `VPN_PORT`, `VPN_PROTO`, `OVPN_PUBLIC_ADDR`.

### `guarded_cargo_test.sh`
Run `cargo test` (or any command) and kill the entire process tree if RSS memory exceeds a limit.
```
./guarded_cargo_test.sh [command...]
CARGO_TEST_MEM_LIMIT_MB=2048 ./guarded_cargo_test.sh
```
Exits with code 137 if the limit is exceeded.
