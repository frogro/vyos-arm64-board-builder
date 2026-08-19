#!/usr/bin/env bash
set -euo pipefail

USAGE="Usage: $0 <board> <rootfs> <boot-dir> <manifest>"

BOARD="${1:?$USAGE}"
ROOTFS="${2:?$USAGE}"
BOOT_DIR="${3:?$USAGE}"
MANIFEST="${4:?$USAGE}"

TEMPLATE_ENV="$BOOT_DIR/raspberrypi-template.env"

[[ -d "$ROOTFS" && -s "$MANIFEST" && -s "$TEMPLATE_ENV" ]] || {
    echo "ERROR: Raspberry Pi rootfs provider input is incomplete" >&2
    exit 1
}

# shellcheck disable=SC1090
source "$TEMPLATE_ENV"

: "${RPI_WLAN_FIRMWARE_ASSET:?RPI_WLAN_FIRMWARE_ASSET missing}"
: "${RPI_WLAN_FIRMWARE_SHA256:?RPI_WLAN_FIRMWARE_SHA256 missing}"

PACKAGE="$BOOT_DIR/artifacts/$RPI_WLAN_FIRMWARE_ASSET"

[[ -s "$PACKAGE" ]] || {
    echo "ERROR: Raspberry Pi WLAN firmware package missing: $PACKAGE" >&2
    exit 1
}

command -v dpkg-deb >/dev/null 2>&1 || {
    echo "ERROR: dpkg-deb is required to install Raspberry Pi WLAN firmware" >&2
    exit 1
}

ACTUAL_SHA256="$(sha256sum "$PACKAGE" | awk '{print $1}')"

[[ "$ACTUAL_SHA256" == "$RPI_WLAN_FIRMWARE_SHA256" ]] || {
    echo "ERROR: Raspberry Pi WLAN firmware checksum changed" >&2
    exit 1
}

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

dpkg-deb -x "$PACKAGE" "$WORK"

SOURCE="$WORK/usr/lib/firmware"
TARGET="$ROOTFS/usr/lib/firmware"
DOC_SOURCE="$WORK/usr/share/doc/firmware-brcm80211"
DOC_TARGET="$ROOTFS/usr/share/doc/firmware-brcm80211"

mkdir -p "$TARGET/brcm" "$TARGET/cypress"

copy_family()
{
    local source_dir="$1"
    local target_dir="$2"
    local pattern="$3"
    local item
    local copied=0

    for item in "$source_dir"/$pattern; do
        [[ -e "$item" || -L "$item" ]] || continue
        cp -a "$item" "$target_dir/"
        copied=1
    done

    [[ "$copied" -eq 1 ]] || {
        echo "ERROR: firmware package lacks $pattern" >&2
        exit 1
    }
}

copy_family "$SOURCE/brcm" "$TARGET/brcm" 'brcmfmac43455-sdio*'
copy_family "$SOURCE/cypress" "$TARGET/cypress" 'cyfmac43455-sdio*'

[[ -s "$DOC_SOURCE/copyright" ]] || {
    echo "ERROR: firmware package license metadata is missing" >&2
    exit 1
}

mkdir -p "$DOC_TARGET"
cp -a "$DOC_SOURCE/." "$DOC_TARGET/"

for required in \
    "$TARGET/brcm/brcmfmac43455-sdio.bin" \
    "$TARGET/brcm/brcmfmac43455-sdio.clm_blob" \
    "$TARGET/brcm/brcmfmac43455-sdio.raspberrypi,5-model-b.txt" \
    "$TARGET/cypress/cyfmac43455-sdio.bin" \
    "$TARGET/cypress/cyfmac43455-sdio.clm_blob" \
    "$DOC_TARGET/copyright"
do
    [[ -e "$required" ]] || {
        echo "ERROR: installed Raspberry Pi firmware is incomplete: $required" >&2
        exit 1
    }
done

echo "Installed BCM43455 WLAN firmware into VyOS rootfs for $BOARD"
