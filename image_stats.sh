#!/usr/bin/env bash

# Check if a directory argument is provided, otherwise default to current directory
SEARCH_DIR="${1:-.}"

# Check if ImageMagick is installed
if ! command -v identify &> /dev/null; then
    echo "Error: ImageMagick is not installed. Please install it to use this script."
    exit 1
fi

# Print Markdown Table Header
echo "| Filename | Width | Height | Aspect Ratio |"
echo "| :--- | :--- | :--- | :--- |"

# Enable nullglob to handle cases where no images match patterns
shopt -s nullglob

# Iterate through common image extensions in the specified directory
for file in "$SEARCH_DIR"/*.{jpg,jpeg,png,gif,webp,bmp,tiff,svg}; do
    # Verify file exists (sanity check for nullglob edge cases)
    [[ -e "$file" ]] || continue

    # Extract filename only (remove path)
    filename=$(basename "$file")

    # Get width and height using identify
    # -format "%w %h" outputs width and height separated by a space
    read -r width height <<< $(identify -format "%w %h" "$file" 2>/dev/null)

    # Check if we successfully got dimensions (e.g., file wasn't corrupted)
    if [[ -n "$width" && -n "$height" ]]; then
        # Calculate aspect ratio using bc for floating point precision (4 decimal places)
        # We append ":1" to the output purely for the visual format requested (e.g., 1.7778:1)
        # Note: If you want X:Y format (e.g. 16:9), the math is much more complex (GCD)
        # The prompt asked for precision like 4.0001:3. 
        # Usually floating point aspect ratios are expressed as N:1. 
        # Below calculates Width / Height.
        
        ratio=$(echo "scale=4; $width / $height" | bc)
        
        # If you specifically wanted the second number to be something other than 1 
        # (like the 4.0001:3 example implies), we can just normalize to height of 1 (Result:1)
        # or we need to know the target denominator. 
        # Standard convention for floating point AR is Width/Height : 1.
        
        echo "| $filename | $width | $height | ${ratio}:1 |"
    else
        echo "| $filename | Error | Error | N/A |"
    fi
done

shopt -u nullglob
