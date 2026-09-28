#!/bin/bash
set -euo pipefail
cd /work
[[ $(uname -m) == aarch64 ]]
bash enable-native-pack.sh
export TMPDIR=/work/assembly-tmp
export KIOSK_F=yes KIOSK_F_GPU_FIRMWARE=mali-arch10.8
export VYOS_1X_PREBUILT=/work/cli-artifacts KIOSK_F_RUNTIME=/work/runtime-artifacts
export OUTPUT_EXTRA_SECTORS=32768
export KVM_CACHED_COPY_BINARY=/work/cached-launch
export KIOSK_F_TEST_KERNEL=/work/panthor-artifacts
IMG=/work/output/vyos-999.202609250800-rock-5b-network-tailscale-kvm-kiosk.img
[[ ! -e "$IMG" ]]
bash repo/tools/assemble-board-image.sh rock-5b current /work/base-expanded.img "$IMG"
bash repo/tools/create-system-image-iso.sh rock-5b "$IMG" /work/output
sgdisk -v "$IMG"
bash verify-full.sh
xz -T4 -3 --keep "$IMG"
xz --test "$IMG.xz"
cd output
for f in *.img.xz *.iso; do sha256sum "$f" > "$f.sha256"; done
sha256sum -c ./*.sha256
printf 'FULL_BUILD_AND_VERIFICATION_COMPLETE\n'

python3 /work/manifest.py

python3 /work/inventory.py
