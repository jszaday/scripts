#!/usr/bin/env bash

echo "Padding numbers to 4 digits..."
echo "------------------------------"

for file in *; do
    # Skip directories
    if [[ -d "$file" ]]; then continue; fi

    # Extract filename and extension
    filename=$(basename -- "$file")
    extension="${filename##*.}"
    name_no_ext="${filename%.*}"

    # Regex check: Only rename if the filename is purely numbers
    if [[ "$name_no_ext" =~ ^[0-9]+$ ]]; then
        
        # printf with %04d handles the padding automatically
        # 1 -> 0001, 25 -> 0025, etc.
        new_name=$(printf "%04d.%s" "$name_no_ext" "$extension")

        # Only rename if the name actually needs changing
        if [[ "$file" != "$new_name" ]]; then
            # Check for collisions (don't overwrite existing files)
            if [[ -e "$new_name" ]]; then
                echo "[SKIP] Target '$new_name' already exists."
            else
                mv "$file" "$new_name"
                echo "[RENAMED] $file -> $new_name"
            fi
        fi
    fi
done
