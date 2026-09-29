#!/bin/bash
set -euo pipefail
base=/mnt/entwicklung/projekte/VyOS/arm/vyos-arm64-board-builder/tmp/av1-iommu-test4
out=/mnt/entwicklung/projekte/VyOS/arm/vyos-arm64-board-builder/tmp/av1-reset-candidates-20260922
mount --make-rprivate /
mount --bind "$out/kbuild" "$base/kbuild"
mount --bind "$out/vsi-iommu.c" "$base/source/drivers/iommu/vsi-iommu.c"
# Build through original paths in a private mount namespace, preserving .cmd reuse.
make -C "$base/source" O="$base/kbuild" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j1 Image
cp "$base/kbuild/arch/arm64/boot/Image" "$out/Image"
sha256sum "$out/Image" > "$out/Image.sha256"
echo CANDIDATE_IMAGE_OK
