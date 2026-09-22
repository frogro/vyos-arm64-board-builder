#!/usr/bin/env bash
set -euo pipefail

BOARD="${1:?Usage: $0 <board> <image> <boot-dir> <efi-start-sector> <efi-sectors>}"
IMAGE="${2:?Usage: $0 <board> <image> <boot-dir> <efi-start-sector> <efi-sectors>}"
BOOT_DIR="${3:?Usage: $0 <board> <image> <boot-dir> <efi-start-sector> <efi-sectors>}"
EFI_START="${4:?Usage: $0 <board> <image> <boot-dir> <efi-start-sector> <efi-sectors>}"
EFI_SECTORS="${5:?Usage: $0 <board> <image> <boot-dir> <efi-start-sector> <efi-sectors>}"

PLATFORM_INSTALL="$BOOT_DIR/metadata/platform_install.sh"
ARTIFACTS="$BOOT_DIR/artifacts"

[[ -s "$PLATFORM_INSTALL" ]] || {
    echo "ERROR: platform_install.sh missing: $PLATFORM_INSTALL" >&2
    exit 1
}

[[ -d "$ARTIFACTS" ]] || {
    echo "ERROR: U-Boot artifacts missing: $ARTIFACTS" >&2
    exit 1
}

#
# Armbian generated this function after all board/family hooks were
# evaluated. It is therefore authoritative for the board's raw
# bootloader installation method.
#
# shellcheck disable=SC1090
source "$PLATFORM_INSTALL"

type write_uboot_platform >/dev/null 2>&1 || {
    echo "ERROR: platform_install.sh does not define write_uboot_platform" >&2
    exit 1
}

#
# platform_install.sh contains the package's original /usr/lib path.
# Our extracted build artifacts live here instead.
#
DIR="$ARTIFACTS"

SECTOR_SIZE=512

#
# Safety guard: raw U-Boot installation must not touch the EFI
# filesystem region used by the VyOS image.
#
EFI_HASH_BEFORE="$(
    dd \
        if="$IMAGE" \
        bs="$SECTOR_SIZE" \
        skip="$EFI_START" \
        count="$EFI_SECTORS" \
        status=none |
    sha256sum |
    awk '{print $1}'
)"

echo "Installing Armbian U-Boot for $BOARD"
echo "Artifact directory: $DIR"

write_uboot_platform \
    "$DIR" \
    "$IMAGE"

sync

EFI_HASH_AFTER="$(
    dd \
        if="$IMAGE" \
        bs="$SECTOR_SIZE" \
        skip="$EFI_START" \
        count="$EFI_SECTORS" \
        status=none |
    sha256sum |
    awk '{print $1}'
)"

[[ "$EFI_HASH_BEFORE" == "$EFI_HASH_AFTER" ]] || {
    echo "ERROR: U-Boot installation modified the EFI partition region" >&2
    exit 1
}

sgdisk --verify "$IMAGE" >/dev/null || {
    echo "ERROR: U-Boot installation damaged GPT metadata" >&2
    exit 1
}

echo "Armbian U-Boot installation completed without EFI/GPT overlap."
