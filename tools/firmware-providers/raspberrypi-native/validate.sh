#!/usr/bin/env bash
set -euo pipefail

BOARD="${1:?Usage: $0 <board> <firmware-device> <artifacts>}"
DEVICE="${2:?Usage: $0 <board> <firmware-device> <artifacts>}"
ARTIFACTS="${3:?Usage: $0 <board> <firmware-device> <artifacts>}"

for cmd in fdtoverlay fdtget; do
    command -v "$cmd" >/dev/null 2>&1 || {
        echo "ERROR: Raspberry Pi validation requires $cmd" >&2
        exit 1
    }
done

fsck.vfat -n "$DEVICE"

WORK="$(mktemp -d)"
D0_RESULT="$(mktemp)"
cleanup()
{
    set +e
    mountpoint -q "$WORK" && umount "$WORK"
    rmdir "$WORK" 2>/dev/null || true
    rm -f "$D0_RESULT"
}
trap cleanup EXIT

mount -o ro "$DEVICE" "$WORK"

for required in \
    config.txt \
    cmdline.txt \
    vmlinuz \
    initrd.img \
    bcm2712-rpi-5-b.dtb \
    overlays/bcm2712d0.dtbo
do
    [[ -s "$WORK/$required" ]] || {
        echo "ERROR: Raspberry Pi validation missing $required" >&2
        exit 1
    }
done

cmp -s "$WORK/vmlinuz" "$ARTIFACTS/Image" || {
    echo "ERROR: Raspberry Pi FAT kernel differs from build artifact" >&2
    exit 1
}

grep -Eq '(^|[[:space:]])boot=live([[:space:]]|$)' "$WORK/cmdline.txt"
grep -Eq '(^|[[:space:]])vyos-union=/boot/' "$WORK/cmdline.txt"

[[ "$(grep -Ec '^[[:space:]]*dtoverlay=bcm2712d0[[:space:]]*$' \
    "$WORK/config.txt")" -eq 1 ]] || {
    echo "ERROR: Raspberry Pi D0 overlay must be enabled exactly once" >&2
    exit 1
}

fdtoverlay \
    -i "$WORK/bcm2712-rpi-5-b.dtb" \
    -o "$D0_RESULT" \
    "$WORK/overlays/bcm2712d0.dtbo"

[[ "$(fdtget -t bx \
    "$WORK/bcm2712-rpi-5-b.dtb" \
    /soc@107c000000/mmc@1100000/wifi@1 \
    local-mac-address)" == "0 0 0 0 0 0" ]]

[[ "$(fdtget -t s \
    "$WORK/bcm2712-rpi-5-b.dtb" \
    /aliases \
    wifi0)" == "/soc@107c000000/mmc@1100000/wifi@1" ]]

grep -Eq '^CONFIG_DRM_VC4=(y|m)$' "$ARTIFACTS/kernel.config"
grep -Eq '^CONFIG_DRM_V3D=(y|m)$' "$ARTIFACTS/kernel.config"

echo "Raspberry Pi firmware partition validation passed for $BOARD"
