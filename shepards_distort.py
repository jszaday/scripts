#!/usr/bin/env python3
# shepards_distort.py — apply randomized Shepard's warp distortion to an image.
# Usage: ./shepards_distort.py input.png output.png [--points 10] [--magnitude 2] [--angle 45] [--box-size 2] [--power 4.0]
#
# Requires: pip install wand   +   ImageMagick on PATH

import argparse
import math
import random
from collections import namedtuple

from wand.image import Image

Point = namedtuple("Point", ["x", "y", "i", "j"])


def generate_points(width, height, n, magnitude, angle, box_size):
    c = round(math.sqrt(width ** 2 + height ** 2))
    clamp = lambda x, lim: min(max(round(x), 0), lim)

    lb = (width  * (box_size - 1)) // (2 * box_size)
    la = (height * (box_size - 1)) // (2 * box_size)

    points = []
    for _ in range(n):
        x = random.randrange(lb, lb + width  // box_size)
        y = random.randrange(la, la + height // box_size)
        d = random.randrange(c // magnitude)
        alpha = random.randrange(angle, 360 - angle)
        i = x + d * math.cos(alpha)
        j = y + d * math.sin(alpha)
        points.append(Point(x, y, clamp(i, width), clamp(j, height)))
    return points


def main():
    parser = argparse.ArgumentParser(
        description="Apply randomized Shepard's warp distortion to an image."
    )
    parser.add_argument("input",  help="Input image path")
    parser.add_argument("output", help="Output image path")
    parser.add_argument("--points",    type=int,   default=10,  help="Number of distortion control points (default: 10)")
    parser.add_argument("--magnitude", type=int,   default=2,   help="Distortion magnitude divisor — smaller = larger displacement (default: 2)")
    parser.add_argument("--angle",     type=int,   default=45,  help="Minimum angle for displacement vectors in degrees (default: 45)")
    parser.add_argument("--box-size",  type=int,   default=2,   help="Fraction of image area used for control points (default: 2)")
    parser.add_argument("--power",     type=float, default=4.0, help="Shepard's power parameter — higher = more localized warping (default: 4.0)")
    args = parser.parse_args()

    with Image(filename=args.input) as img:
        points = generate_points(img.width, img.height, args.points, args.magnitude, args.angle, args.box_size)

        img.virtual_pixel = "mirror"
        img.artifacts["shepards:power"] = str(args.power)
        img.distort("shepards", sum(points, ()))
        img.save(filename=args.output)

    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
