#!/usr/bin/env bash
set -euo pipefail

BOARD="${1:?Usage: $0 <board> <hardware-branch> <boot-branch> <boot-dir>}"
HW_BRANCH="${2:?Usage: $0 <board> <hardware-branch> <boot-branch> <boot-dir>}"
BOOT_BRANCH="${3:?Usage: $0 <board> <hardware-branch> <boot-branch> <boot-dir>}"
BOOT_DIR="${4:?Usage: $0 <board> <hardware-branch> <boot-branch> <boot-dir>}"

: "${FIRMWARE_URL:?Raspberry Pi firmware source URL missing}"
: "${FIRMWARE_ASSET:?Raspberry Pi firmware asset name missing}"

EXPECTED_SHA256="633f8e88af3e67b720783db5637e1371afed5c761d2885ffc87c6ba6292c8a78"
ARTIFACTS="$BOOT_DIR/artifacts"
IMAGE="$ARTIFACTS/$FIRMWARE_ASSET"

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

cat > "$BOOT_DIR/raspberrypi-template.env" <<EOF_TEMPLATE
RPI_TEMPLATE_ASSET=$(printf '%q' "$FIRMWARE_ASSET")
RPI_TEMPLATE_SHA256=$(printf '%q' "$EXPECTED_SHA256")
RPI_TEMPLATE_SOURCE=$(printf '%q' "$FIRMWARE_URL")
EOF_TEMPLATE

echo "Raspberry Pi boot template verified: $FIRMWARE_ASSET"
