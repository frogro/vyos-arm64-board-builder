#!/bin/bash
set -euo pipefail
cd /work
out=/work/wayland-image-20260923
mkdir -p "$out/output" "$out/mount" "$out/artifacts"
exec > >(tee -a "$out/build.log") 2>&1
printf 'running\n' > "$out/status"
loop=''
cleanup() {
 for item in run sys proc dev; do mountpoint -q "$out/root/$item" && umount -R "$out/root/$item" || true; done
 mountpoint -q "$out/mount" && umount "$out/mount" || true
 [[ -z $loop ]] || losetup -d "$loop"
}
trap cleanup EXIT
trap 'printf "failed\n" > "$out/status"' ERR
base=vyos-999.202609191955-rock-5b-network-tailscale-kvm-kiosk
# Discard only the interrupted repack copy; original SD/ISO artifacts remain.
old=/work/revised-20260923/output/$base.img
if [[ -f $old ]]; then
 while read -r dev; do [[ -z $dev ]] || losetup -d "$dev"; done < <(losetup -j "$old" -n -O NAME)
 rm -- "$old"
fi
loop=$(losetup --find --show --read-only --partscan "/work/output/$base.img")
udevadm settle
IFS=: read -r major minor < "/sys/class/block/$(basename "$loop")p3/dev"
[[ -b ${loop}p3 ]] || mknod "${loop}p3" b "$major" "$minor"
mount -o ro "${loop}p3" "$out/mount"
boot="$out/mount/boot/999.202609191955"
unsquashfs -excludes -processors 4 -d "$out/root" "$boot/999.202609191955.squashfs" usr/share/vyos-arm64-board-builder/kiosk-runtime/runtime.tar
umount "$out/mount"; losetup -d "$loop"; loop=''
# The runtime archive is moved, not duplicated, while disk space is tight.
runtime="$out/root/usr/share/vyos-arm64-board-builder/kiosk-runtime"
mv /work/wayland-artifacts-20260923/runtime.tar "$runtime/runtime.tar"
cp /work/wayland-artifacts-20260923/runtime.json "$runtime/runtime.json"
install -m755 /work/repack-inputs-20260923/vyos-arm64-setup-links.sh "$out/root/usr/local/sbin/vyos-arm64-setup-links.sh"
install -m755 /work/repack-inputs-20260923/setup-kiosk.py "$out/root/usr/local/sbin/vyarm-kiosk-setup"
mount --rbind /dev "$out/root/dev"; mount --make-rslave "$out/root/dev"
mount -t proc proc "$out/root/proc"
mount --rbind /sys "$out/root/sys"; mount --make-rslave "$out/root/sys"
mount -t tmpfs tmpfs "$out/root/run"
/work/repo/tools/install-kvm-cli.sh "$out/root" /cli/output yes yes yes
chroot "$out/root" python3 -c "from vyos.xml_ref import owner; assert owner(['container','name','test','kiosk','display-backend'],with_tag=True)=='container'"
for item in run sys proc dev; do umount -R "$out/root/$item"; done
printf '%s\n' 'Wayland14 DRM integration 20260923. X11 default retained. Live compositor smoke passed; full new-image first boot, interactive touch and Sunshine Wayland not validated.' > "$runtime/packaging-revision.txt"
mksquashfs "$out/root" "$out/rootfs.squashfs" -noappend -comp xz -processors 6
mv "$runtime/runtime.tar" /work/wayland-artifacts-20260923/runtime.tar
rm -rf -- "$out/root"
image="$out/output/$base.img"
cp --sparse=always "/work/output/$base.img" "$image"
loop=$(losetup --find --show --partscan "$image")
udevadm settle
IFS=: read -r major minor < "/sys/class/block/$(basename "$loop")p3/dev"
[[ -b ${loop}p3 ]] || mknod "${loop}p3" b "$major" "$minor"
mount "${loop}p3" "$out/mount"
cp "$out/rootfs.squashfs" "$out/mount/boot/999.202609191955/999.202609191955.squashfs"
sync
umount "$out/mount"; losetup -d "$loop"; loop=''
rm "$out/rootfs.squashfs"
/work/repo/tools/create-system-image-iso.sh rock-5b "$image" "$out/output"
sgdisk -v "$image"
xz -T6 -6 --keep "$image"
xz --test "$image.xz"
(cd "$out/output" && sha256sum *.img.xz *.iso > SHA256SUMS)
cp /work/wayland-artifacts-20260923/runtime.json /cli/output/build.json "$out/output/"
chown -R 1000:1000 "$out"
printf 'complete\n' > "$out/status"
