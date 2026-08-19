#!/usr/bin/env bash
set -euo pipefail

BOARD="${1:?Usage: $0 <board> <image> <boot-dir> <efi-start-sector> <efi-sectors>}"
IMAGE="${2:?Usage: $0 <board> <image> <boot-dir> <efi-start-sector> <efi-sectors>}"
BOOT_DIR="${3:?Usage: $0 <board> <image> <boot-dir> <efi-start-sector> <efi-sectors>}"

TEMPLATE_ENV="$BOOT_DIR/raspberrypi-template.env"
[[ -s "$TEMPLATE_ENV" ]] || {
    echo "ERROR: Raspberry Pi template metadata missing" >&2
    exit 1
}

# shellcheck disable=SC1090
source "$TEMPLATE_ENV"

SOURCE_XZ="$BOOT_DIR/artifacts/$RPI_TEMPLATE_ASSET"
[[ -s "$SOURCE_XZ" ]] || {
    echo "ERROR: Raspberry Pi template image missing: $SOURCE_XZ" >&2
    exit 1
}

for cmd in xz losetup udevadm blkid mkfs.vfat mount umount mountpoint rsync; do
    command -v "$cmd" >/dev/null 2>&1 || {
        echo "ERROR: required command missing: $cmd" >&2
        exit 1
    }
done

WORK="$(mktemp -d)"
SOURCE_IMAGE="$WORK/source.img"
SOURCE_MNT="$WORK/source"
TARGET_MNT="$WORK/target"
SOURCE_LOOP=""
TARGET_LOOP=""
mkdir -p "$SOURCE_MNT" "$TARGET_MNT"

cleanup()
{
    set +e
    mountpoint -q "$TARGET_MNT" && umount "$TARGET_MNT"
    mountpoint -q "$SOURCE_MNT" && umount "$SOURCE_MNT"
    [[ -n "$TARGET_LOOP" ]] && losetup -d "$TARGET_LOOP" 2>/dev/null
    [[ -n "$SOURCE_LOOP" ]] && losetup -d "$SOURCE_LOOP" 2>/dev/null
    rm -rf "$WORK"
}
trap cleanup EXIT

xz -dc "$SOURCE_XZ" > "$SOURCE_IMAGE"
SOURCE_LOOP="$(losetup --find --show --read-only --partscan "$SOURCE_IMAGE")"
TARGET_LOOP="$(losetup --find --show --partscan "$IMAGE")"
udevadm settle

SOURCE_PART="${SOURCE_LOOP}p1"
TARGET_PART="${TARGET_LOOP}p1"

[[ -b "$SOURCE_PART" && -b "$TARGET_PART" ]] || {
    echo "ERROR: Raspberry Pi source/target firmware partition missing" >&2
    exit 1
}

[[ "$(blkid -s TYPE -o value "$SOURCE_PART" 2>/dev/null || true)" == "vfat" ]] || {
    echo "ERROR: Raspberry Pi template partition 1 is not FAT" >&2
    exit 1
}

mkfs.vfat -F 32 -n RPICFG "$TARGET_PART" >/dev/null
mount -o ro "$SOURCE_PART" "$SOURCE_MNT"
mount "$TARGET_PART" "$TARGET_MNT"

for required in config.txt cmdline.txt start4.elf fixup4.dat overlays; do
    [[ -e "$SOURCE_MNT/$required" ]] || {
        echo "ERROR: Raspberry Pi template lacks $required" >&2
        exit 1
    }
done

rsync -rt --delete --modify-window=1 "$SOURCE_MNT/" "$TARGET_MNT/"
sync

echo "Installed pinned Raspberry Pi firmware template for $BOARD"
