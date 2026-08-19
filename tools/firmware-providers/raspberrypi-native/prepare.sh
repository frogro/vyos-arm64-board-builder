#!/usr/bin/env bash
set -euo pipefail

BOARD="${1:?Usage: $0 <board> <hardware-branch> <boot-branch> <boot-dir>}"
HW_BRANCH="${2:?Usage: $0 <board> <hardware-branch> <boot-branch> <boot-dir>}"
BOOT_BRANCH="${3:?Usage: $0 <board> <hardware-branch> <boot-branch> <boot-dir>}"
BOOT_DIR="${4:?Usage: $0 <board> <hardware-branch> <boot-branch> <boot-dir>}"

: "${FIRMWARE_URL:?Raspberry Pi firmware source URL missing}"
: "${FIRMWARE_ASSET:?Raspberry Pi firmware asset name missing}"

EXPECTED_SHA256="633f8e88af3e67b720783db5637e1371afed5c761d2885ffc87c6ba6292c8a78"
WLAN_FIRMWARE_ASSET="firmware-brcm80211_20250410-2_all.deb"
WLAN_FIRMWARE_URL="https://deb.debian.org/debian/pool/non-free-firmware/f/firmware-nonfree/$WLAN_FIRMWARE_ASSET"
WLAN_FIRMWARE_SHA256="266cc703e2299f5253fd1ff9a1fd625d85a2c8e5a88b1a65fcc190ac384ce3d7"
ARTIFACTS="$BOOT_DIR/artifacts"
IMAGE="$ARTIFACTS/$FIRMWARE_ASSET"
WLAN_FIRMWARE="$ARTIFACTS/$WLAN_FIRMWARE_ASSET"

mkdir -p "$ARTIFACTS"

if [[ ! -s "$IMAGE" ]]; then
    curl -fL --retry 4 --retry-delay 5 "$FIRMWARE_URL" -o "$IMAGE"
fi

ACTUAL_SHA256="$(sha256sum "$IMAGE" | awk '{print $1}')"

[[ "$ACTUAL_SHA256" == "$EXPECTED_SHA256" ]] || {
    echo "ERROR: pinned Raspberry Pi boot-template SHA-256 mismatch" >&2
    echo "Expected: $EXPECTED_SHA256" >&2
    echo "Actual:   $ACTUAL_SHA256" >&2
    exit 1
}

if [[ ! -s "$WLAN_FIRMWARE" ]]; then
    curl -fL --retry 4 --retry-delay 5 \
        "$WLAN_FIRMWARE_URL" \
        -o "$WLAN_FIRMWARE"
fi

ACTUAL_WLAN_SHA256="$(sha256sum "$WLAN_FIRMWARE" | awk '{print $1}')"

[[ "$ACTUAL_WLAN_SHA256" == "$WLAN_FIRMWARE_SHA256" ]] || {
    echo "ERROR: pinned BCM43455 firmware SHA-256 mismatch" >&2
    echo "Expected: $WLAN_FIRMWARE_SHA256" >&2
    echo "Actual:   $ACTUAL_WLAN_SHA256" >&2
    exit 1
}

cat > "$BOOT_DIR/raspberrypi-template.env" <<EOF_TEMPLATE
RPI_TEMPLATE_ASSET=$(printf '%q' "$FIRMWARE_ASSET")
RPI_TEMPLATE_SHA256=$(printf '%q' "$EXPECTED_SHA256")
RPI_TEMPLATE_SOURCE=$(printf '%q' "$FIRMWARE_URL")
RPI_WLAN_FIRMWARE_ASSET=$(printf '%q' "$WLAN_FIRMWARE_ASSET")
RPI_WLAN_FIRMWARE_SHA256=$(printf '%q' "$WLAN_FIRMWARE_SHA256")
RPI_WLAN_FIRMWARE_SOURCE=$(printf '%q' "$WLAN_FIRMWARE_URL")
EOF_TEMPLATE

echo "Raspberry Pi boot template verified: $FIRMWARE_ASSET"
echo "Raspberry Pi BCM43455 firmware verified: $WLAN_FIRMWARE_ASSET"
