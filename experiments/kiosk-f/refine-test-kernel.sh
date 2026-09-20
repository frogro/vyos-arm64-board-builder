#!/usr/bin/env bash
# Incremental, local-only second test kernel. Preserve all first-build artifacts.
set -euo pipefail
umask 077
RUN=${1:?Usage: refine-test-kernel.sh COMPLETED_FIRST_RUN}
RUN=$(realpath "$RUN")
HERE=$(cd "$(dirname "$0")" && pwd)
KERNEL="$RUN/source/cache/linux-vyos/linux-6.18.50"
OUT="$RUN/artifacts-v2"
[[ -f "$RUN/artifacts/Image" && -f "$RUN/kbuild/.config" ]]
[[ ! -e "$OUT" ]]
mkdir "$OUT"
cp "$RUN/kbuild/.config" "$OUT/config-before"
cp "$HERE/0001-test-dw-hdmi-qp-select-audio-codec.patch" "$OUT/"
cp "$0" "$OUT/build-script.sh"
git -C "$HERE" rev-parse HEAD > "$OUT/builder-commit"
printf 'building test2: DMA heaps and HDMI codec dependency\n' > "$RUN/status"
trap 'result=$?; if ((result)); then printf "failed test2: %s\n" "$result" > "$RUN/status"; fi' EXIT
patch --batch -d "$KERNEL" -p1 < "$OUT/0001-test-dw-hdmi-qp-select-audio-codec.patch"
"$KERNEL/scripts/config" --file "$RUN/kbuild/.config" \
  --enable DMABUF_HEAPS --enable DMABUF_HEAPS_SYSTEM --enable DMABUF_HEAPS_CMA
KMAKE=(make -C "$KERNEL" O="$RUN/kbuild" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- LOCALVERSION=-vyos-f-test2)
"${KMAKE[@]}" olddefconfig
for required in CONFIG_DMABUF_HEAPS=y CONFIG_DMABUF_HEAPS_SYSTEM=y CONFIG_DMABUF_HEAPS_CMA=y CONFIG_SND_SOC_HDMI_CODEC=m CONFIG_SND_PCM_ELD=y CONFIG_SND_PCM_IEC958=y CONFIG_INPUT_UINPUT=m CONFIG_HID_MULTITOUCH=m CONFIG_DRM_PANTHOR=m CONFIG_MODULE_SIG_FORCE=y; do
  grep -qx "$required" "$RUN/kbuild/.config" || { echo "Missing: $required"; exit 1; }
done
"$KERNEL/scripts/diffconfig" "$OUT/config-before" "$RUN/kbuild/.config" > "$OUT/config-diff.txt"
cp "$RUN/kbuild/.config" "$OUT/kernel.config"
"${KMAKE[@]}" -j2 Image Image.gz modules rockchip/rk3588-rock-5b.dtb
"${KMAKE[@]}" INSTALL_MOD_PATH="$RUN/modules-v2" modules_install
cp "$RUN/kbuild/arch/arm64/boot/Image" "$RUN/kbuild/arch/arm64/boot/Image.gz" "$RUN/kbuild/Module.symvers" "$RUN/kbuild/System.map" "$OUT/"
cp "$RUN/kbuild/arch/arm64/boot/dts/rockchip/rk3588-rock-5b.dtb" "$OUT/"
"${KMAKE[@]}" -s kernelrelease > "$OUT/kernel.release"
tar --exclude='*/build' --exclude='*/source' -C "$RUN/modules-v2" -cJf "$OUT/modules.tar.xz" lib
chmod 600 "$RUN/kbuild/certs/signing_key.pem"
sha256sum "$OUT/"* > "$RUN/SHA256SUMS-v2"
printf 'complete test2: artifacts-v2 only, not installed or boot-tested\n' > "$RUN/status"
