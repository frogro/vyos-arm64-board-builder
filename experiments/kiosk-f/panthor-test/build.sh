#!/bin/bash
set -euo pipefail
REPO=$(pwd)
WORK=${1:?new absolute work directory}
mkdir -p "$WORK"
cd "$WORK"
gh release download adf-compare-inputs-20260927 --repo "$GITHUB_REPOSITORY" --pattern panthor-kernel-source.tar.gz --pattern panthor-reference.config
sha256sum -c "$REPO/experiments/kiosk-f/panthor-test/inputs.sha256"
tar -xzf panthor-kernel-source.tar.gz
python3 "$REPO/experiments/kiosk-f/sunshine/cached-maps/prepare.py" kernel-source source
mkdir kbuild artifacts modules
cp panthor-reference.config kbuild/.config
source/scripts/config --file kbuild/.config --set-str LOCALVERSION '' --disable LOCALVERSION_AUTO
make -C source O="$WORK/kbuild" ARCH=arm64 LOCALVERSION=-vyos-panthor-cache-test olddefconfig
make -C source O="$WORK/kbuild" ARCH=arm64 LOCALVERSION=-vyos-panthor-cache-test -j4 Image modules rockchip/rk3588-rock-5b.dtb
make -C source O="$WORK/kbuild" ARCH=arm64 LOCALVERSION=-vyos-panthor-cache-test INSTALL_MOD_PATH="$WORK/modules" INSTALL_MOD_STRIP=1 -j4 modules_install
KREL=$(make -s -C source O="$WORK/kbuild" ARCH=arm64 LOCALVERSION=-vyos-panthor-cache-test kernelrelease)
[[ "$KREL" == 6.18.50-vyos-panthor-cache-test ]]
git init vyos-build
git -C vyos-build remote add origin https://github.com/vyos/vyos-build.git
git -C vyos-build fetch --depth 1 origin d1394291337eb0274e026145a4c6245207c1c71d
git -C vyos-build checkout --detach FETCH_HEAD
bash "$REPO/tools/build-vyos-oot-modules.sh" --vyos-tree "$WORK/vyos-build" --kernel-build "$WORK/kbuild" --modules-root "$WORK/modules" --kernel-release "$KREL" --localversion -vyos-panthor-cache-test --work-dir "$WORK/oot"
# Never include private keys or host/build symlinks in the distributable payload.
find modules -type l \( -name build -o -name source \) -delete
cp kbuild/arch/arm64/boot/Image kbuild/System.map artifacts/
cp kbuild/.config artifacts/kernel.config
cp kbuild/arch/arm64/boot/dts/rockchip/rk3588-rock-5b.dtb artifacts/board.dtb
printf '%s\n' "$KREL" > artifacts/kernel.release
tar -C modules -cf artifacts/modules.tar lib
(cd artifacts && sha256sum Image System.map kernel.config kernel.release board.dtb modules.tar > SHA256SUMS)
printf 'PANTHOR_TEST_KERNEL_BUILD_OK\n'
