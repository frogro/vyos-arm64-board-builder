#!/bin/bash
# Extend a verified, extracted A-D ISO with matching F artifacts. Offline only.
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
WORK=$(realpath "${1:?prepared working directory}")
VERSION=${2:?unique test image version}
[[ $EUID == 0 && $WORK != / && $VERSION =~ ^[A-Za-z0-9._-]+$ ]]
ROOT=$WORK/rootfs
KERNEL=$WORK/kernel-artifacts
[[ -d $ROOT/var/lib/dpkg && -f $WORK/iso-ad/version.json ]]
[[ ! -e $WORK/assembly-complete && ! -e $WORK/original-ad-modules ]]
(cd "$KERNEL" && sha256sum -c SHA256SUMS)
KREL=$(cat "$KERNEL/kernel.release")
[[ $KREL =~ ^[A-Za-z0-9._+-]+$ ]]
mkdir -p "$ROOT"/{dev,proc,sys,run}
cleanup() {
    for p in run sys proc dev; do
        if mountpoint -q "$ROOT/$p"; then umount -R "$ROOT/$p"; fi
    done
}
trap cleanup EXIT
mount --rbind /dev "$ROOT/dev"
mount --make-rslave "$ROOT/dev"
mount -t proc proc "$ROOT/proc"
mount --rbind /sys "$ROOT/sys"
mount --make-rslave "$ROOT/sys"
mount -t tmpfs tmpfs "$ROOT/run"
"$REPO/tools/install-kvm-cli.sh" "$ROOT" "$WORK/cli-artifacts" yes yes yes
python3 "$REPO/tools/patch-vyos-image-info.py" "$ROOT"
python3 "$REPO/tools/patch-vyos-system-image-dtb.py" "$ROOT"
python3 "$REPO/tools/patch-vyos-arm-cpu-opmode.py" "$ROOT"
bash "$REPO/tools/finalize-vyos-rootfs.sh" rock-5b "$ROOT" yes yes network-tailscale-kvm-kiosk yes rk3588-synopsys-hdmirx rk3588-hdmirx+generic-v4l2 yes yes
python3 "$REPO/experiments/kiosk-f/host/install.py" --rootfs "$ROOT" --cache "$WORK/firmware-cache" --panthor-arch10-8
bash "$REPO/experiments/kiosk-f/host/protect-grub-dtb.sh" "$ROOT" rockchip/rk3588-rock-5b.dtb
python3 "$REPO/experiments/kiosk-f/image/stage-runtime.py" "$ROOT" "$WORK/runtime-artifacts"
# Preserve the original module tree outside the image; install the complete set.
mv "$ROOT/usr/lib/modules/$KREL" "$WORK/original-ad-modules"
tar -xf "$KERNEL/modules.tar" -C "$ROOT/usr" lib/modules
cp "$KERNEL/Image" "$ROOT/boot/vmlinuz-$KREL"
cp "$KERNEL/kernel.config" "$ROOT/boot/config-$KREL"
cp "$KERNEL/System.map" "$ROOT/boot/System.map-$KREL"
chroot "$ROOT" depmod "$KREL"
chroot "$ROOT" update-initramfs -c -k "$KREL"
python3 - "$ROOT" "$VERSION" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]);p=root/'usr/share/vyos/version.json'
m=json.loads(p.read_text());m['version']=sys.argv[2]
m['build_comment']='Local A-D plus F candidate; preserved A-D base, matched CLI/kernel and validated Wayland runtime'
p.write_text(json.dumps(m)+'\n')
PY
# Validate preserved configuration without embedding credentials in the image.
# /run is the temporary tmpfs mounted above and is removed before packaging.
if [[ -f $WORK/private-backup/config-before.tar ]]; then
    tar -xOf "$WORK/private-backup/config-before.tar" config/config.boot > "$ROOT/run/config-validation.boot"
    chmod 600 "$ROOT/run/config-validation.boot"
    chroot "$ROOT" python3 -c 'from pathlib import Path; from vyos.configtree import ConfigTree, validate_tree; result=validate_tree(ConfigTree(config_string=Path("/run/config-validation.boot").read_text())); assert not result, "Saved configuration fails new CLI schema validation"; print("Saved configuration passes new CLI schema validation")'
    rm "$ROOT/run/config-validation.boot"
fi
cleanup
trap - EXIT
ISO=$WORK/iso-adf
mkdir "$ISO"
cp -a "$WORK/iso-ad/." "$ISO/"
cp "$KERNEL/Image" "$ISO/live/vmlinuz"
cp "$ROOT/boot/initrd.img-$KREL" "$ISO/live/initrd.img"
cp "$KERNEL/dtb/rockchip/rk3588-rock-5b.dtb" "$ISO/live/dtb/rockchip/"
cp "$ROOT/usr/share/vyos/version.json" "$ISO/version.json"
python3 - "$ISO/board-manifest.json" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1]);m=json.loads(p.read_text())
assert m['board']=='rock-5b' and m['profile']=='network-tailscale-kvm'
m['profile']='network-tailscale-kvm-kiosk';m['features']['kiosk_f']=True
p.write_text(json.dumps(m,indent=2)+'\n')
PY
# Replace only the new workspace copy of the original squashfs.
rm "$ISO/live/filesystem.squashfs"
mksquashfs "$ROOT" "$ISO/live/filesystem.squashfs" -noappend -comp xz -processors 2 -mem 1G
(cd "$ISO" && find . -type f ! -name sha256sum.txt -print0 | sort -z | xargs -0 sha256sum > sha256sum.txt && sha256sum -c sha256sum.txt)
mkdir -p "$WORK/output"
OUT=$WORK/output/vyos-$VERSION-rock-5b-network-tailscale-kvm-kiosk.iso
[[ ! -e $OUT ]]
xorriso -as mkisofs -r -J -V VYOS_ARM64 -o "$OUT" "$ISO"
(cd "$WORK/output" && sha256sum "$(basename "$OUT")" > "$(basename "$OUT").sha256")
printf '%s\n' "$OUT" > "$WORK/assembly-complete"
