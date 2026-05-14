#!/usr/bin/env python3
# tile_images.py — tile images in a brick pattern with optional rotation, then center-crop to target size.
# Usage: ./tile_images.py tile1.png tile2.png --width 1920 --height 1080 [--angle 45] [--scale 1.0]

import argparse
import sys
from PIL import Image, ImageOps
import math
from itertools import cycle


def load_and_validate_images(image_paths):
    """Load images and validate they are all the same size."""
    images = []
    reference_size = None
    
    for path in image_paths:
        try:
            img = Image.open(path)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            if reference_size is None:
                reference_size = img.size
            else:
                assert img.size == reference_size, f"Image {path} size {img.size} doesn't match reference size {reference_size}"
            
            images.append(img)
        except Exception as e:
            input(f"Error loading image {path}: {e}.\nPress Enter to continue; this file will be ignored. Ctrl-C to abort. > ")
    
    return images, reference_size


def rotate_image(img, angle):
    """Rotate image by given angle, expanding canvas to fit."""
    return img.rotate(angle, expand=True, fillcolor=(0, 0, 0, 0))


def scale_image(img, scale_factor):
    """Scale image by given factor."""
    if scale_factor == 1.0:
        return img
    
    new_width = int(img.width * scale_factor)
    new_height = int(img.height * scale_factor)
    return img.resize((new_width, new_height), Image.Resampling.LANCZOS)


def tile_images(images, canvas_width, canvas_height, tile_width, tile_height):
    """Tile unrotated images across the canvas in brick pattern, cycling through the image list."""
    from itertools import cycle
    
    canvas = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))
    
    img_iter = cycle(images)
    
    # Calculate how many tiles we need (with some extra for safety)
    tiles_x = math.ceil(canvas_width / tile_width) + 1
    tiles_y = math.ceil(canvas_height / tile_height) + 1
    
    for row in range(tiles_y):
        y = row * tile_height
        
        # Odd rows get offset by half tile width for brick pattern
        is_odd_row = (row % 2 == 1)
        offset_x = (tile_width // 2) if is_odd_row else 0

        for col in range(tiles_x):
            x = col * tile_width + offset_x
            
            # Skip if completely outside canvas
            if x >= canvas_width or y >= canvas_height:
                continue
                
            img = next(img_iter)
            canvas.paste(img, (x, y), img)

        next(img_iter)
        next(img_iter)

    return canvas


def center_crop(img, target_width, target_height):
    """Center crop image to target dimensions."""
    img_width, img_height = img.size
    
    # Calculate crop box
    left = (img_width - target_width) // 2
    top = (img_height - target_height) // 2
    right = left + target_width
    bottom = top + target_height
    
    return img.crop((left, top, right, bottom))


def main():
    parser = argparse.ArgumentParser(description="Tile PNGs with angle control.")
    parser.add_argument("images", nargs="+", help="List of .png files to tile.")
    parser.add_argument("--width", type=int, required=True, help="Output width in pixels.")
    parser.add_argument("--height", type=int, required=True, help="Output height in pixels.")
    parser.add_argument("--scale", type=float, default=1.0, help="Scaling factor to apply to images before tiling them.")
    parser.add_argument("--angle", type=float, default=45, help="Rotation angle in degrees.")
    parser.add_argument("--output", default="tiled_output.png", help="Output filename.")
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.width <= 0 or args.height <= 0:
        print("Error: Width and height must be positive integers.")
        sys.exit(1)
    
    if args.scale <= 0:
        print("Error: Scale factor must be positive.")
        sys.exit(1)
    
    # Load and validate images
    print(f"Loading {len(args.images)} images...")
    images, original_size = load_and_validate_images(args.images)
    print(f"All images validated with size: {original_size}")
    
    # Scale images (but don't rotate them yet)
    scaled_images = []
    for img in images:
        scaled_img = scale_image(img, args.scale)
        scaled_images.append(scaled_img)
    
    # Get dimensions of scaled tiles
    tile_width, tile_height = scaled_images[0].size
    print(f"Scaled tile size: {tile_width}x{tile_height}")
    
    # Create large canvas (4x the target size)
    canvas_width = args.width * 4
    canvas_height = args.height * 4
    print(f"Creating canvas: {canvas_width}x{canvas_height}")
    
    # Tile the unrotated images in brick pattern
    print("Tiling images...")
    tiled_canvas = tile_images(scaled_images, canvas_width, canvas_height, tile_width, tile_height)
    
    # Now rotate the entire canvas
    print(f"Rotating entire canvas by {args.angle} degrees...")
    rotated_canvas = rotate_image(tiled_canvas, args.angle)
    
    # Center crop to target size
    print(f"Center cropping to {args.width}x{args.height}")
    final_image = center_crop(rotated_canvas, args.width, args.height)
    
    # Save the result
    print(f"Saving to {args.output}")
    final_image.save(args.output, 'PNG')
    print("Done!")


if __name__ == "__main__":
    main()
