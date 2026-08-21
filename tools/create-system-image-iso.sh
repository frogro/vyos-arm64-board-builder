#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BOARD="${1:?Usage: $0 <board> <board.img> <output-dir>}"
IMAGE="${2:?Usage: $0 <board> <board.img> <output-dir>}"
OUTPUT_DIR="${3:?Usage: $0 <board> <board.img> <output-dir>}"

MANIFEST="$ROOT/work/build/$BOARD/boot/boot-manifest.env"
IDENTITY_TOOL="$ROOT/tools/release-identity.py"
FEATURE_ENV="$ROOT/work/build/$BOARD/selection/feature-profiles.env"
KVM_HARDWARE_ENV="$ROOT/work/build/$BOARD/selection/kvm-hardware.env"

die()
{
    echo "ERROR: $*" >&2
    exit 1
}

need()
{
    command -v "$1" >/dev/null 2>&1 ||
        die "required command not found: $1"
}

for cmd in \
    blkid \
    find \
    fdtget \
    losetup \
    mount \
    mountpoint \
    python3 \
    sha256sum \
    sort \
    unsquashfs \
    udevadm \
    xorriso
do
    need "$cmd"
done

[[ $EUID -eq 0 ]] || die "create-system-image-iso.sh must run as root"
[[ -s "$IMAGE" ]] || die "board image missing: $IMAGE"
[[ -s "$MANIFEST" ]] || die "boot manifest missing: $MANIFEST"
[[ -x "$IDENTITY_TOOL" ]] || die "release identity tool missing"

# shellcheck disable=SC1090
source "$MANIFEST"

BUILD_PROFILE="base"
EXTENDED_NETWORK="no"
TAILSCALE_SUBNET_ROUTER="no"
KVM_OVER_IP="no"
KVM_HARDWARE_PROVIDER="disabled"
KVM_CAPTURE_BACKEND="disabled"
KVM_HID_GADGET="no"
if [[ -f "$FEATURE_ENV" ]]; then
    # shellcheck disable=SC1090
    source "$FEATURE_ENV"
fi
if [[ -f "$KVM_HARDWARE_ENV" ]]; then
    # shellcheck disable=SC1090
    source "$KVM_HARDWARE_ENV"
fi

[[ -n "${BOOT_FDT_FILE:-}" ]] || die "BOOT_FDT_FILE missing from manifest"
[[ -n "${BOARD_NAME:-}" ]] || die "BOARD_NAME missing from manifest"
[[ -n "${FIRMWARE_PROVIDER:-}" ]] || die "FIRMWARE_PROVIDER missing from manifest"

case "$FIRMWARE_PROVIDER" in
    edk2-rk3588)
        UPDATE_PROVIDER="efi-firmware-dtb"
        ;;
    raspberrypi-native)
        UPDATE_PROVIDER="firmware-files"
        ;;
    *)
        UPDATE_PROVIDER="grub-version-dtb"
        ;;
esac

mkdir -p "$OUTPUT_DIR"

WORK="$(mktemp -d)"
PERSISTENCE_MNT="$WORK/persistence"
ISO_ROOT="$WORK/iso"
ISO_CHECK="$WORK/iso-check"
LOOP=""

mkdir -p "$PERSISTENCE_MNT" "$ISO_ROOT/live" "$ISO_CHECK"

cleanup()
{
    set +e
    mountpoint -q "$ISO_CHECK" && umount "$ISO_CHECK"
    mountpoint -q "$PERSISTENCE_MNT" && umount "$PERSISTENCE_MNT"
    [[ -n "$LOOP" ]] && losetup -d "$LOOP" 2>/dev/null
    rm -rf "$WORK"
}

trap cleanup EXIT

LOOP="$(
    losetup \
        --find \
        --show \
        --read-only \
        --partscan \
        "$IMAGE"
)"

udevadm settle

PERSISTENCE_DEV=""
for part in "${LOOP}"p*; do
    [[ -b "$part" ]] || continue
    if [[ "$(blkid -s LABEL -o value "$part" 2>/dev/null || true)" == \
          "persistence" ]]; then
        PERSISTENCE_DEV="$part"
        break
    fi
done

[[ -n "$PERSISTENCE_DEV" ]] || die "persistence partition not found"

mount -o ro "$PERSISTENCE_DEV" "$PERSISTENCE_MNT"

VERSION_DIR="$(
    find "$PERSISTENCE_MNT/boot" \
        -mindepth 1 \
        -maxdepth 1 \
        -type d \
        -exec test -s '{}/vmlinuz' ';' \
        -exec test -s '{}/initrd.img' ';' \
        -print |
    sort |
    tail -1
)"

[[ -n "$VERSION_DIR" ]] || die "VyOS version directory not found"

VERSION="$(basename "$VERSION_DIR")"
SQUASH="$(
    find "$VERSION_DIR" \
        -maxdepth 1 \
        -type f \
        -name '*.squashfs' \
        -print \
        -quit
)"
DTB="$VERSION_DIR/dtb/$BOOT_FDT_FILE"

[[ -s "$SQUASH" ]] || die "VyOS SquashFS not found"
[[ -s "$DTB" ]] || die "board DTB missing from image: $DTB"

RELEASE_ENV="$OUTPUT_DIR/release.env"
python3 "$IDENTITY_TOOL" \
    --version "$VERSION" \
    --board "$BOARD" \
    --profile "$BUILD_PROFILE" \
    --output "$RELEASE_ENV"

# shellcheck disable=SC1090
source "$RELEASE_ENV"

ISO="$OUTPUT_DIR/${RELEASE_BASENAME}.iso"

install -D -m 0644 "$VERSION_DIR/vmlinuz" "$ISO_ROOT/live/vmlinuz"
install -D -m 0644 "$VERSION_DIR/initrd.img" "$ISO_ROOT/live/initrd.img"
install -D -m 0644 "$SQUASH" "$ISO_ROOT/live/filesystem.squashfs"
install -D -m 0644 "$DTB" "$ISO_ROOT/live/dtb/$BOOT_FDT_FILE"

unsquashfs -cat "$SQUASH" usr/share/vyos/version.json \
    > "$ISO_ROOT/version.json"

read -r -a COMPATIBLE <<< "$(fdtget -t s "$DTB" / compatible)"

python3 - \
    "$ISO_ROOT/board-manifest.json" \
    "$BOARD" \
    "$BOARD_NAME" \
    "$BOOT_FDT_FILE" \
    "$FIRMWARE_PROVIDER" \
    "$UPDATE_PROVIDER" \
    "$BUILD_PROFILE" \
    "$EXTENDED_NETWORK" \
    "$TAILSCALE_SUBNET_ROUTER" \
    "$KVM_OVER_IP" \
    "$KVM_HARDWARE_PROVIDER" \
    "$KVM_CAPTURE_BACKEND" \
    "$KVM_HID_GADGET" \
    "${COMPATIBLE[@]}" <<'PY'
import json
from pathlib import Path
import sys

output, board, name, dtb, firmware, update_provider, profile, extended_network, tailscale, kvm, kvm_provider, capture_backend, hid_gadget, *compatible = sys.argv[1:]
Path(output).write_text(json.dumps({
    "schema": 3,
    "architecture": "arm64",
    "board": board,
    "board_name": name,
    "compatible": compatible,
    "device_tree": dtb,
    "firmware_provider": firmware,
    "update_provider": update_provider,
    "profile": profile,
    "profile_compatibility": "exact",
    "features": {
        "extended_network": extended_network == "yes",
        "tailscale_subnet_router": tailscale == "yes",
        "kvm_over_ip": kvm == "yes",
    },
    "kvm": {
        "hardware_provider": kvm_provider,
        "capture_backend": capture_backend,
        "hid_gadget": hid_gadget,
    },
}, indent=2) + "\n")
PY

install -m 0644 "$ISO_ROOT/board-manifest.json" \
    "$OUTPUT_DIR/board-manifest.json"

(
    cd "$ISO_ROOT"
    find . -type f ! -name sha256sum.txt -print0 |
        sort -z |
        xargs -0 sha256sum > sha256sum.txt
    sha256sum -c sha256sum.txt
)

rm -f "$ISO"
xorriso \
    -as mkisofs \
    -r \
    -J \
    -V VYOS_ARM64 \
    -o "$ISO" \
    "$ISO_ROOT"

mount -o loop,ro "$ISO" "$ISO_CHECK"
(
    cd "$ISO_CHECK"
    sha256sum -c sha256sum.txt
)
umount "$ISO_CHECK"

(
    cd "$OUTPUT_DIR"
    sha256sum "${RELEASE_BASENAME}.iso" \
        > "${RELEASE_BASENAME}.iso.sha256"
)

cat >> "$RELEASE_ENV" <<EOF
UPDATE_PROVIDER=${UPDATE_PROVIDER}
UPDATE_ISO=${RELEASE_BASENAME}.iso
UPDATE_ISO_SHA256=${RELEASE_BASENAME}.iso.sha256
INSTALL_IMAGE=${RELEASE_BASENAME}.img.xz
INSTALL_IMAGE_SHA256=${RELEASE_BASENAME}.img.xz.sha256
EOF

echo "Created VyOS system-image ISO: $ISO"
echo "Release metadata: $RELEASE_ENV"
