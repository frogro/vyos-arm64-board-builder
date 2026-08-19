#!/usr/bin/env bash
set -euo pipefail

BOARD="${1:?Usage: $0 <board> <firmware-device> <artifacts>}"
DEVICE="${2:?Usage: $0 <board> <firmware-device> <artifacts>}"
ARTIFACTS="${3:?Usage: $0 <board> <firmware-device> <artifacts>}"

fsck.vfat -n "$DEVICE"

WORK="$(mktemp -d)"
cleanup()
{
    set +e
    mountpoint -q "$WORK" && umount "$WORK"
    rmdir "$WORK" 2>/dev/null || true
}
trap cleanup EXIT

mount -o ro "$DEVICE" "$WORK"

for required in config.txt cmdline.txt vmlinuz initrd.img bcm2712-rpi-5-b.dtb; do
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

echo "Raspberry Pi firmware partition validation passed for $BOARD"
