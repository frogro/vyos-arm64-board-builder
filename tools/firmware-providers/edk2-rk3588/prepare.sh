#!/usr/bin/env bash
set -euo pipefail

BOARD="${1:?Usage: $0 <board> <hardware-branch> <boot-branch> <boot-dir>}"
HW_BRANCH="${2:?Usage: $0 <board> <hardware-branch> <boot-branch> <boot-dir>}"
BOOT_BRANCH="${3:?Usage: $0 <board> <hardware-branch> <boot-branch> <boot-dir>}"
BOOT_DIR="${4:?Usage: $0 <board> <hardware-branch> <boot-branch> <boot-dir>}"

: "${FIRMWARE_VARIANT:?FIRMWARE_VARIANT missing}"
: "${FIRMWARE_RELEASE:?FIRMWARE_RELEASE missing}"
: "${FIRMWARE_ASSET:?FIRMWARE_ASSET missing}"
: "${FIRMWARE_URL:?FIRMWARE_URL missing}"

OUT="$BOOT_DIR/edk2"
IMAGE="$OUT/$FIRMWARE_ASSET"

mkdir -p "$OUT"

echo "Downloading EDK2 firmware:"
echo "  Board:   $BOARD"
echo "  Variant: $FIRMWARE_VARIANT"
echo "  Release: $FIRMWARE_RELEASE"
echo "  Asset:   $FIRMWARE_ASSET"

curl \
    --fail \
    --location \
    --retry 3 \
    --output "$IMAGE" \
    "$FIRMWARE_URL"

[[ -s "$IMAGE" ]] || {
    echo "ERROR: downloaded EDK2 image is empty: $IMAGE" >&2
    exit 1
}

sha256sum "$IMAGE"
