#!/bin/bash

# auto_format_sd.sh - Format microSD cards with specific cluster sizes based on capacity.
# Requirements: macOS, diskutil, sudo access for newfs.

set -e

usage() {
    echo "Usage: $0 <device_path> [volume_name]"
    echo "Example: $0 /dev/disk4 SDCARD"
    echo ""
    echo "This script formats the given disk according to the following rules:"
    echo "  4-32 GiB    -> 32 KiB (FAT32)"
    echo "  64-128 GiB  -> 128 KiB (exFAT)"
    echo "  128-512 GiB -> 256 KiB (exFAT)"
    echo "  > 512 GiB   -> 512 KiB (exFAT)"
    echo ""
    echo "WARNING: All data on the target device will be lost!"
    exit 1
}

DEVICE=$1
NAME=${2:-SDCARD}

if [ -z "$DEVICE" ]; then
    usage
fi

# Ensure we have sudo early
sudo -v

# Normalize device path (e.g. disk4 -> /dev/disk4)
if [[ ! "$DEVICE" =~ ^/dev/ ]]; then
    DEVICE="/dev/$DEVICE"
fi

if [ ! -b "$DEVICE" ]; then
    echo "Error: $DEVICE is not a block device."
    exit 1
fi

# Get disk info
INFO=$(diskutil info "$DEVICE")
if [ $? -ne 0 ]; then
    echo "Error: Could not get info for $DEVICE."
    exit 1
fi

# Extract size in bytes
SIZE_BYTES=$(echo "$INFO" | grep "Disk Size" | sed -E 's/.* \(([0-9]+) Bytes\).*/\1/')
if [ -z "$SIZE_BYTES" ]; then
    echo "Error: Could not determine size of $DEVICE."
    exit 1
fi

# Extract sector size
SECTOR_SIZE=$(echo "$INFO" | grep "Device Block Size" | awk '{print $4}')
SECTOR_SIZE=${SECTOR_SIZE:-512}

GIB=$((1024 * 1024 * 1024))
SIZE_GIB=$(echo "$SIZE_BYTES / $GIB" | bc 2>/dev/null || awk "BEGIN {print int($SIZE_BYTES / $GIB)}")

echo "--------------------------------------------------"
echo "Device:       $DEVICE"
echo "Size:         $SIZE_GIB GiB ($SIZE_BYTES bytes)"
echo "Sector Size:  $SECTOR_SIZE bytes"
echo "Volume Name:  $NAME"

# Determine FS and Cluster Size
if [ "$SIZE_BYTES" -le $((32 * GIB)) ]; then
    FS_TYPE="FAT32"
    CLUSTER_SIZE_KB=32
    # newfs_msdos uses sectors per cluster
    SPC=$((32 * 1024 / SECTOR_SIZE))
    NEWFS_CMD="newfs_msdos -F 32 -c $SPC"
    ERASE_FS="MS-DOS FAT32"
elif [ "$SIZE_BYTES" -le $((128 * GIB)) ]; then
    FS_TYPE="exFAT"
    CLUSTER_SIZE_KB=128
    NEWFS_CMD="newfs_exfat -b $((128 * 1024))"
    ERASE_FS="ExFAT"
elif [ "$SIZE_BYTES" -le $((512 * GIB)) ]; then
    FS_TYPE="exFAT"
    CLUSTER_SIZE_KB=256
    NEWFS_CMD="newfs_exfat -b $((256 * 1024))"
    ERASE_FS="ExFAT"
else
    FS_TYPE="exFAT"
    CLUSTER_SIZE_KB=512
    NEWFS_CMD="newfs_exfat -b $((512 * 1024))"
    ERASE_FS="ExFAT"
fi

echo "Target FS:    $FS_TYPE"
echo "Cluster Size: ${CLUSTER_SIZE_KB} KiB"
echo "--------------------------------------------------"

# Safety check for internal disks
if echo "$INFO" | grep -q "Internal: Yes"; then
    echo "!!! WARNING: $DEVICE appears to be an INTERNAL disk !!!"
    read -p "Are you absolutely sure you want to continue? [type YES]: " confirm_internal
    if [ "$confirm_internal" != "YES" ]; then
        echo "Aborted."
        exit 1
    fi
fi

read -p "Proceed with erasing $DEVICE? [y/N]: " confirm
if [[ ! "$confirm" =~ ^[yY]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Step 1: Prepare the disk
echo "Unmounting all volumes on $DEVICE..."
diskutil unmountDisk "$DEVICE" || true

echo "Initializing disk with MBR partition map..."
diskutil eraseDisk "$ERASE_FS" TEMP MBR "$DEVICE"

# Step 2: Identify the partition
# For MBR it's almost always s1
PARTITION="${DEVICE}s1"
RPARTITION=$(echo "$PARTITION" | sed 's/disk/rdisk/')

# Step 3: Unmount for raw access
echo "Unmounting $PARTITION..."
diskutil unmount "$PARTITION" || true

# Step 4: Apply the specific cluster size
echo "Applying custom cluster size ($CLUSTER_SIZE_KB KiB)..."
sudo $NEWFS_CMD -v "$NAME" "$RPARTITION"

# Step 5: Mount the new volume
echo "Mounting volume..."
diskutil mount "$PARTITION"

echo "--------------------------------------------------"
echo "Success! $DEVICE formatted as $FS_TYPE with ${CLUSTER_SIZE_KB}KB clusters."
echo "Volume '$NAME' is ready."
