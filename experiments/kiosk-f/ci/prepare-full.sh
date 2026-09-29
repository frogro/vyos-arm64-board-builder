#!/bin/bash
set -euo pipefail
cd /work
mkdir -p repo output assembly-tmp
[[ ! -e repo/tools/assemble-board-image.sh ]]
tar -xf repo.tar -C repo
(cd kernel-artifacts && sha256sum -c SHA256SUMS)
(cd input-ad && sha256sum -c vyos-999.202609250800-rock-5b-network-tailscale-kvm.img.xz.sha256)
python3 - <<'PY'
import hashlib,json,pathlib
p=pathlib.Path('runtime-artifacts');m=json.loads((p/'runtime.json').read_text())
a=list(p.glob('*.tar*'));assert len(a)==1,a
with a[0].open('rb') as f: h=hashlib.file_digest(f,'sha256').hexdigest()
assert h==m['archive_sha256']
print('Validated Kiosk runtime:',m['image_id'])
PY
B=repo/work/build/rock-5b
mkdir -p "$B/modules" repo/cache/kiosk-f-firmware
cp -a input-ad/artifacts input-ad/boot input-ad/selection "$B/"
cp -a kernel-artifacts/Image kernel-artifacts/System.map kernel-artifacts/kernel.config kernel-artifacts/kernel.release kernel-artifacts/dtb "$B/artifacts/"
tar -xf kernel-artifacts/modules.tar -C "$B/modules"
cp -a firmware-cache/. repo/cache/kiosk-f-firmware/
cat >> "$B/selection/feature-profiles.env" <<'ENV'
KIOSK_F=yes
KIOSK_F_GPU_FIRMWARE=mali-arch10.8
BUILD_PROFILE=network-tailscale-kvm-kiosk
ENV
# Expand only this disposable build input, never a physical disk.
xz -dc input-ad/vyos-999.202609250800-rock-5b-network-tailscale-kvm.img.xz > base-expanded.img
truncate -s 12G base-expanded.img
sgdisk -e base-expanded.img
START=$(sgdisk -i 3 base-expanded.img | awk '/First sector:/ {print $3}')
[[ $START =~ ^[0-9]+$ ]]
sgdisk -d 3 -n 3:${START}:0 -t 3:8300 -c 3:persistence base-expanded.img
LOOP=$(losetup --find --show --partscan base-expanded.img)
trap 'losetup -d "$LOOP"' EXIT
udevadm settle
e2fsck -pf "${LOOP}p3" || [[ $? == 1 ]]
resize2fs "${LOOP}p3"
losetup -d "$LOOP"
trap - EXIT
touch preparation-complete
