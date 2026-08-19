#!/usr/bin/env bash
set -euo pipefail

BOARD="${1:?Usage: $0 <board> <image> <boot-dir> <efi-start-sector> <efi-sectors>}"
IMAGE="${2:?Usage: $0 <board> <image> <boot-dir> <efi-start-sector> <efi-sectors>}"
BOOT_DIR="${3:?Usage: $0 <board> <image> <boot-dir> <efi-start-sector> <efi-sectors>}"
EFI_START="${4:?Usage: $0 <board> <image> <boot-dir> <efi-start-sector> <efi-sectors>}"
EFI_SECTORS="${5:?Usage: $0 <board> <image> <boot-dir> <efi-start-sector> <efi-sectors>}"

MANIFEST="$BOOT_DIR/boot-manifest.env"

[[ -f "$MANIFEST" ]] || {
    echo "ERROR: boot manifest missing: $MANIFEST" >&2
    exit 1
}

# shellcheck disable=SC1090
source "$MANIFEST"

: "${FIRMWARE_ASSET:?FIRMWARE_ASSET missing from boot manifest}"

EDK2_IMAGE="$BOOT_DIR/edk2/$FIRMWARE_ASSET"

[[ -s "$EDK2_IMAGE" ]] || {
    echo "ERROR: EDK2 firmware missing: $EDK2_IMAGE" >&2
    exit 1
}

SECTOR_SIZE=512
SKIP_SECTORS="${FIRMWARE_SKIP_SECTORS:-64}"

EDK2_BYTES="$(stat -c '%s' "$EDK2_IMAGE")"
EDK2_SECTORS=$(((EDK2_BYTES + SECTOR_SIZE - 1) / SECTOR_SIZE))

(( EDK2_SECTORS <= EFI_START )) || {
    echo "ERROR: EDK2 firmware would overlap EFI partition" >&2
    exit 1
}

echo "Installing EDK2 firmware for $BOARD"
echo "Preserving GPT sectors 0..$((SKIP_SECTORS - 1))"

dd \
    if="$EDK2_IMAGE" \
    of="$IMAGE" \
    bs="$SECTOR_SIZE" \
    skip="$SKIP_SECTORS" \
    seek="$SKIP_SECTORS" \
    conv=notrunc,fsync \
    status=progress
