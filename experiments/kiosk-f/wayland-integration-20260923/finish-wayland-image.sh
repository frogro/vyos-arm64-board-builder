#!/bin/bash
set -euo pipefail
out=/work/wayland-image-20260923
base=vyos-999.202609191955-rock-5b-network-tailscale-kvm-kiosk
exec > >(tee -a "$out/build.log") 2>&1
printf 'verifying-and-compressing\n' > "$out/status"
loop=$(losetup --find --show --read-only "$out/output/$base.iso")
IFS=: read -r major minor < "/sys/class/block/$(basename "$loop")/dev"
[[ -b $loop ]] || mknod "$loop" b "$major" "$minor"
mkdir -p "$out/check-iso"
trap 'mountpoint -q "$out/check-iso" && umount "$out/check-iso" || true; losetup -d "$loop" 2>/dev/null || true' EXIT
mount -o ro "$loop" "$out/check-iso"
(cd "$out/check-iso" && sha256sum -c sha256sum.txt)
unsquashfs -cat "$out/check-iso/live/filesystem.squashfs" usr/lib/python3/dist-packages/vyos/kiosk.py > "$out/kiosk.py.checked"
grep -q display_backend "$out/kiosk.py.checked"
unsquashfs -cat "$out/check-iso/live/filesystem.squashfs" usr/share/vyos-arm64-board-builder/kiosk-runtime/runtime.json > "$out/runtime.checked.json"
python3 - "$out/runtime.checked.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1])); assert m['image']=='localhost/vyarm-kiosk:wayland-corrected-20260923'; assert m['wayland_drm']=='weston14'
PY
unsquashfs -cat "$out/check-iso/live/filesystem.squashfs" usr/local/sbin/vyarm-kiosk-setup > "$out/setup.checked.py"
grep -q display-backend "$out/setup.checked.py"
umount "$out/check-iso"; losetup -d "$loop"; trap - EXIT
sgdisk -v "$out/output/$base.img"
xz -T6 -6 --keep "$out/output/$base.img"
xz --test "$out/output/$base.img.xz"
(cd "$out/output" && sha256sum *.img.xz *.iso > SHA256SUMS && sha256sum "$base.iso" > "$base.iso.sha256" && sha256sum "$base.img.xz" > "$base.img.xz.sha256")
cp /work/wayland-artifacts-20260923/runtime.json /cli/output/build.json "$out/output/"
printf '\nUPDATE_PROVIDER=efi-firmware-dtb\nUPDATE_ISO=%s.iso\nUPDATE_ISO_SHA256=%s.iso.sha256\nINSTALL_IMAGE=%s.img.xz\nINSTALL_IMAGE_SHA256=%s.img.xz.sha256\n' "$base" "$base" "$base" "$base" >> "$out/output/release.env"
chown -R 1000:1000 "$out"
printf 'complete\n' > "$out/status"
