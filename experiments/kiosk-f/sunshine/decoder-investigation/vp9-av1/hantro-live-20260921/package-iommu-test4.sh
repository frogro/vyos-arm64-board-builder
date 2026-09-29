#!/usr/bin/env bash
# Package a completed isolated build; never install or select a boot entry.
set -euo pipefail
umask 077
run=$(realpath "${1:?Usage: package-iommu-test4.sh TEST4_RUN_DIR}")
release=6.18.50-vyos-f-test4-av1-iommu
[[ -f "$run/full-build.status" ]] && grep -qx 'exit_code=0' "$run/full-build.status"
grep -qx FULL_BUILD_OK "$run/full-build.log"
[[ $(make -s -C "$run/source" O="$run/kbuild" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- kernelrelease) == "$release" ]]
[[ ! -e "$run/artifacts" ]] || { echo 'Artifacts already exist; inspect before replacing'; exit 1; }
make -C "$run/source" O="$run/kbuild" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- INSTALL_MOD_PATH="$run/stage-test4" modules_install
module_dir="$run/stage-test4/lib/modules/$release"
[[ -s "$module_dir/modules.dep" ]]
hantro=$(find "$module_dir/kernel/drivers/media/platform/verisilicon" -name 'hantro-vpu.ko*' -type f)
[[ -n "$hantro" && $(modinfo -F signer "$hantro") != '' ]]
modinfo -F vermagic "$hantro" | grep -q "^$release "
grep -qx CONFIG_VSI_IOMMU=y "$run/kbuild/.config"
grep -q ' vsi_iommu_restore_ctx$' "$run/kbuild/System.map"
mkdir "$run/artifacts"
cp "$run/kbuild/arch/arm64/boot/Image" "$run/artifacts/"
cp "$run/kbuild/arch/arm64/boot/dts/rockchip/rk3588-rock-5b.dtb" "$run/artifacts/"
cp "$run/kbuild/.config" "$run/artifacts/kernel.config"
printf '%s\n' "$release" > "$run/artifacts/kernel.release"
tar --exclude='*/build' --exclude='*/source' -cf "$run/artifacts/modules.tar" -C "$run/stage-test4/lib/modules" "$release"
(cd "$run/artifacts" && sha256sum Image rk3588-rock-5b.dtb kernel.config kernel.release modules.tar > SHA256SUMS && sha256sum -c SHA256SUMS)
printf 'packaged=%s\nnot_installed=true\n' "$(date -Is)" > "$run/package.status"
