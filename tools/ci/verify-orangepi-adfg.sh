#!/bin/bash
# Validate exactly the selected profiles in the SD/eMMC rootfs before ISO creation.
set -euo pipefail
image=${1:?Image required}
loop=$(losetup --find --show --read-only --partscan "$image")
verify=$(mktemp -d)
trap 'mountpoint -q "$verify/mnt" && umount "$verify/mnt"; losetup -d "$loop"; rm -rf "$verify"' EXIT
mkdir "$verify/mnt"
udevadm settle
partition=
for candidate in "${loop}"p*; do
    if [[ $(blkid -s LABEL -o value "$candidate") == persistence ]]; then partition=$candidate; break; fi
done
[[ -n "$partition" ]]
mount -o ro "$partition" "$verify/mnt"
squash=$(find "$verify/mnt/boot" -name '*.squashfs' -print -quit)
[[ -s $squash ]]
python3 tools/ci/verify-selected-rootfs.py "$squash"
