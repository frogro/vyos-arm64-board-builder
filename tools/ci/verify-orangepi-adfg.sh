#!/bin/bash
# Validate exactly the selected profiles in the SD/eMMC rootfs before ISO creation.
set -euo pipefail
case "$BOARD" in rock-5b|orangepi5-plus|raspberry-pi-5) ;; *) exit 1 ;; esac
image=${1:?Image required}
loop=$(losetup --find --show --read-only --partscan "$image")
verify=$(mktemp -d)
trap 'mountpoint -q "$verify/mnt" && umount "$verify/mnt"; losetup -d "$loop"; rm -rf "$verify"' EXIT
mkdir "$verify/mnt"
udevadm settle
mount -o ro "${loop}p3" "$verify/mnt"
squash=$(find "$verify/mnt/boot" -name '*.squashfs' -print -quit)
[[ -s $squash ]]
python3 tools/ci/verify-selected-rootfs.py "$squash"
