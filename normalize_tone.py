#!/usr/bin/env python3
# normalize_tone.py — normalize color tone across JPEG images using Reinhard color transfer.
# Usage: ./normalize_tone.py [--preset neutral|warm|cool] [--ref ref.jpg] [--strength 0..1]
import argparse
import glob
import os
import numpy as np
import cv2 as cv
from tqdm import tqdm

def grayworld_wb(img_bgr):
    img = img_bgr.astype(np.float32) + 1e-6
    mean = img.reshape(-1,3).mean(axis=0)
    g = mean.mean() / mean
    out = img * g
    return np.clip(out, 0, 255).astype(np.uint8)

def image_lab_stats(img_bgr, downscale_max=512):
    h, w = img_bgr.shape[:2]
    scale = min(1.0, downscale_max / max(h, w))
    if scale < 1.0:
        img_small = cv.resize(img_bgr, (int(w*scale), int(h*scale)), interpolation=cv.INTER_AREA)
    else:
        img_small = img_bgr
    lab = cv.cvtColor(img_small, cv.COLOR_BGR2LAB).reshape(-1,3).astype(np.float32)
    mu = lab.mean(axis=0)
    sigma = lab.std(axis=0) + 1e-6
    return mu, sigma

def reinhard_match_to_target(img_bgr, target_mu, target_sigma, strength=1.0):
    lab = cv.cvtColor(img_bgr, cv.COLOR_BGR2LAB).astype(np.float32)
    mu, sigma = lab.reshape(-1,3).mean(axis=0), lab.reshape(-1,3).std(axis=0) + 1e-6
    norm = (lab - mu) / sigma
    mu_blend = (1-strength)*mu + strength*target_mu
    sigma_blend = (1-strength)*sigma + strength*target_sigma
    matched = norm * sigma_blend + mu_blend
    matched = np.clip(matched, 0, 255).astype(np.uint8)
    return cv.cvtColor(matched, cv.COLOR_LAB2BGR)

def preset_to_lab_target(preset, base_sigma):
    if preset == "neutral":
        mu = np.array([128, 128, 128], dtype=np.float32)
    elif preset == "warm":
        mu = np.array([128, 138, 150], dtype=np.float32)
    elif preset == "cool":
        mu = np.array([128, 120, 118], dtype=np.float32)
    else:
        raise ValueError("unknown preset")
    sigma = np.array([base_sigma[0], base_sigma[1]*0.6, base_sigma[2]*0.6], dtype=np.float32)
    mu = np.clip(mu, 0, 255)
    sigma = np.clip(sigma, 1.0, 128.0)
    return mu, sigma

def main():
    ap = argparse.ArgumentParser(description="Normalize color tone across JPGs in cwd.")
    ap.add_argument("--preset", choices=["neutral","warm","cool"], default="neutral",
                    help="target tone if no --ref provided")
    ap.add_argument("--ref", type=str, default=None, help="reference image path (overrides preset)")
    ap.add_argument("--strength", type=float, default=1.0, help="0..1; 1 = full match")
    ap.add_argument("--no-wb", action="store_true", help="disable gray-world white-balance")
    ap.add_argument("--match-lum", action="store_true", help="also align luminance std strongly")
    ap.add_argument("--outdir", type=str, default="normalized")
    args = ap.parse_args()

    paths = sorted(glob.glob("*.jpg") + glob.glob("*.jpeg") + glob.glob("*.JPG") + glob.glob("*.JPEG"))
    if not paths:
        print("No JPGs in cwd.")
        return
    os.makedirs(args.outdir, exist_ok=True)

    mu_list, sigma_list = [], []
    print("Analyzing tone distribution...")
    for p in tqdm(paths, desc="Collecting stats", ncols=80):
        img = cv.imread(p, cv.IMREAD_COLOR)
        if img is None:
            continue
        if not args.no_wb:
            img = grayworld_wb(img)
        mu, sigma = image_lab_stats(img)
        mu_list.append(mu); sigma_list.append(sigma)

    if args.ref:
        ref = cv.imread(args.ref, cv.IMREAD_COLOR)
        if ref is None:
            raise SystemExit(f"Reference not readable: {args.ref}")
        if not args.no_wb:
            ref = grayworld_wb(ref)
        target_mu, target_sigma = image_lab_stats(ref)
    else:
        base_sigma = np.median(np.stack(sigma_list, axis=0), axis=0)
        target_mu, target_sigma = preset_to_lab_target(args.preset, base_sigma)

    if args.match_lum:
        target_sigma[0] = np.median(np.stack(sigma_list), axis=0)[0] * 0.5

    print("Normalizing color tones...")
    for p in tqdm(paths, desc="Processing images", ncols=80):
        img = cv.imread(p, cv.IMREAD_COLOR)
        if img is None:
            continue
        if not args.no_wb:
            img = grayworld_wb(img)
        out = reinhard_match_to_target(img, target_mu, target_sigma, strength=args.strength)
        cv.imwrite(os.path.join(args.outdir, os.path.basename(p)), out)

if __name__ == "__main__":
    main()
