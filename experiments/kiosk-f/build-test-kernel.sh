#!/usr/bin/env bash
# Isolated ROCK experiment. Never installs, publishes, or edits normal workflows.
set -euo pipefail
umask 077
REPO=$(cd "$(dirname "$0")/../.." && pwd)
RUN=${1:?Usage: build-test-kernel.sh NEW_RUN_DIR_WITH_reference/kernel.config}
RUN=$(realpath "$RUN")
[[ -s "$RUN/reference/kernel.config" ]] || exit 1
[[ ! -e "$RUN/source" ]] || { echo 'Use a fresh run directory'; exit 1; }
mkdir -p "$RUN/artifacts" "$RUN/kbuild" "$RUN/gnupg"
export GNUPGHOME="$RUN/gnupg"
printf 'preparing\n' > "$RUN/status"
trap 'result=$?; if ((result)); then printf "failed: %s\n" "$result" > "$RUN/status"; fi' EXIT
git clone --no-hardlinks --no-checkout "$REPO" "$RUN/source"
git -C "$RUN/source" checkout --detach "$(git -C "$REPO" rev-parse HEAD)"
ROOT_DIR="$RUN/source"
source "$ROOT_DIR/lib/ui.sh"
source "$ROOT_DIR/sources/vyos.sh"
export VYOS_REF=4571978c8542a1f996af8a4913c787eecfb0b15d
vyos_fetch
vyos_kernel_prepare 6.18.50 profiles/kvm-hardware/kernel-patches/rk3588-synopsys-hdmirx
KERNEL=$(vyos_kernel_source_dir 6.18.50)
patch --batch -d "$KERNEL" -p1 < "$ROOT_DIR/experiments/kiosk-f/sunshine/rga-investigation/0001-diagnostic-bt601-destination-mode.patch"
cp "$RUN/reference/kernel.config" "$RUN/kbuild/.config"
"$KERNEL/scripts/config" --file "$RUN/kbuild/.config" \
  --module INPUT_UINPUT --module HID_MULTITOUCH --module DRM_PANTHOR \
  --enable PM --enable PM_DEVFREQ --enable PM_OPP \
  --set-str LOCALVERSION '' --disable LOCALVERSION_AUTO
KMAKE=(make -C "$KERNEL" O="$RUN/kbuild" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- LOCALVERSION=-vyos-f-test1)
"${KMAKE[@]}" olddefconfig
for required in CONFIG_INPUT_UINPUT=m CONFIG_HID_MULTITOUCH=m CONFIG_DRM_PANTHOR=m CONFIG_ROCKCHIP_MPP_SERVICE=y CONFIG_ROCKCHIP_MPP_RKVENC2=y CONFIG_VIDEO_ROCKCHIP_RGA=m CONFIG_MODULE_SIG_FORCE=y; do
  grep -qx "$required" "$RUN/kbuild/.config" || { echo "Missing: $required"; exit 1; }
done
"$KERNEL/scripts/diffconfig" "$RUN/reference/kernel.config" "$RUN/kbuild/.config" > "$RUN/artifacts/config-diff.txt"
printf 'compiling\n' > "$RUN/status"
"${KMAKE[@]}" -j2 Image Image.gz modules rockchip/rk3588-rock-5b.dtb
"${KMAKE[@]}" INSTALL_MOD_PATH="$RUN/modules" modules_install
cp "$RUN/kbuild/arch/arm64/boot/Image" "$RUN/kbuild/arch/arm64/boot/Image.gz" "$RUN/kbuild/Module.symvers" "$RUN/kbuild/System.map" "$RUN/artifacts/"
cp "$RUN/kbuild/.config" "$RUN/artifacts/kernel.config"
cp "$RUN/kbuild/arch/arm64/boot/dts/rockchip/rk3588-rock-5b.dtb" "$RUN/artifacts/"
"${KMAKE[@]}" -s kernelrelease > "$RUN/artifacts/kernel.release"
tar --exclude='*/build' --exclude='*/source' -C "$RUN/modules" -cJf "$RUN/artifacts/modules.tar.xz" lib
# Keep private signing material in restricted kbuild, NEVER in artifacts.
chmod 600 "$RUN/kbuild/certs/signing_key.pem"
sha256sum "$RUN/artifacts/"* > "$RUN/SHA256SUMS"
printf 'complete: kernel artifacts only, not installed or boot-tested\n' > "$RUN/status"
