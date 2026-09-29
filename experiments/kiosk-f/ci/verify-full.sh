#!/bin/bash
set -euo pipefail
cd /work
bash /work/enable-native-pack.sh
V=/work/verification
mkdir -p "$V"/{sd,iso,root}
IMG=/work/output/vyos-999.202609250800-rock-5b-network-tailscale-kvm-kiosk.img
ISO=${IMG%.img}.iso
LOOP=$(losetup --find --show --read-only --partscan "$IMG")
cleanup() { umount "$V/root/run" 2>/dev/null || true; umount "$V/iso" 2>/dev/null || true; umount "$V/sd" 2>/dev/null || true; losetup -d "$LOOP"; }
trap cleanup EXIT
udevadm settle
e2fsck -fn "${LOOP}p3"
mount -o ro "${LOOP}p3" "$V/sd"
mount -o loop,ro "$ISO" "$V/iso"
SD="$V/sd/boot/999.202609250800"
cmp "$SD/vmlinuz" kernel-artifacts/Image
cmp "$SD/dtb/rockchip/rk3588-rock-5b.dtb" kernel-artifacts/dtb/rockchip/rk3588-rock-5b.dtb
cmp "$SD/vmlinuz" "$V/iso/live/vmlinuz"
cmp "$SD/initrd.img" "$V/iso/live/initrd.img"
SQUASH=$(find "$SD" -maxdepth 1 -name '*.squashfs' -print -quit)
cmp "$SQUASH" "$V/iso/live/filesystem.squashfs"
(cd "$V/iso" && sha256sum -c sha256sum.txt)
unsquashfs -d "$V/root" -f "$SQUASH" >/work/verification-extract.log
cmp repo/experiments/kiosk-f/cli/kiosk.py "$V/root/usr/lib/python3/dist-packages/vyos/kiosk.py"
cmp repo/experiments/kiosk-f/cli/remote.py "$V/root/usr/lib/python3/dist-packages/vyos/kiosk_remote.py"
cmp repo/experiments/kiosk-f/systemd/remote-hardware.py "$V/root/usr/local/libexec/vyos-kiosk-remote-hardware"
cmp repo/experiments/kiosk-f/sunshine/input-bridge/bridge.py "$V/root/usr/local/libexec/vyos-kiosk-sunshine-inputs"
cmp /work/cached-launch "$V/root/usr/libexec/vyos/vyos-kvm-cached-launch"
test -f "$V/root/etc/systemd/system/vyos-kiosk-remote-hardware.service"
cmp repo/experiments/kiosk-f/systemd/reconcile-inputs.py "$V/root/usr/local/libexec/vyos-kiosk-reconcile-inputs"
cmp runtime-artifacts/runtime.json "$V/root/usr/share/vyos-arm64-board-builder/kiosk-runtime/runtime.json"
cmp runtime-artifacts/runtime.tar "$V/root/usr/share/vyos-arm64-board-builder/kiosk-runtime/runtime.tar"
PANTHOR="$V/root/usr/share/vyarm/panthor-test"
for file in Image board.dtb kernel.release; do cmp "panthor-artifacts/$file" "$PANTHOR/$file"; done
cmp repo/experiments/kiosk-f/panthor-test/install-menu.py "$V/root/usr/local/libexec/vyarm-panthor-test-menu"
test -L "$V/root/etc/systemd/system/multi-user.target.wants/vyarm-panthor-test-menu.service"
test -d "$V/root/usr/lib/modules/$(cat panthor-artifacts/kernel.release)"
lsinitramfs "$PANTHOR/initrd.img" > "$V/panthor-initrd-files.txt"
grep -q 'lib/modules/6.18.50-vyos-panthor-cache-test/' "$V/panthor-initrd-files.txt"
grep -q 'arm/mali/arch10.8/mali_csffw.bin' "$V/panthor-initrd-files.txt"
python3 - <<'PY'
import json,pathlib
r=pathlib.Path('/work/verification/root');p=pathlib.Path('/work/cli-artifacts/build.json')
a=json.loads(p.read_text());b=json.loads((r/'usr/share/vyos-arm64-board-builder/native-cli/build.json').read_text());assert a==b
m=json.loads(pathlib.Path('/work/verification/iso/board-manifest.json').read_text());assert m['features']['kiosk_f'] and m['features']['kvm_over_ip'] and m['features']['tailscale_subnet_router'] and m['features']['extended_network'];assert m['profile']=='network-tailscale-kvm-kiosk'
assert 'optional_input' in (r/'usr/libexec/vyos/conf_mode/container.py').read_text()
assert (r/'usr/local/sbin/vyarm-kiosk-setup').is_file()
assert (r/'usr/lib/firmware/arm/mali/arch10.8/mali_csffw.bin').is_file()
assert (r/'etc/systemd/system/rsyslog.service.d/50-vyarm-config-ready.conf').is_file()
assert not list((r/'etc/ssh').glob('ssh_host_*_key'))
op=r/'opt/vyatta/share/vyatta-op/templates'
show=(op/'show/log/console-server/node.def').read_text()
monitor=(op/'monitor/log/console-server/node.def').read_text()
assert 'conserver-server.service' in show and '--follow' not in show
assert 'conserver-server.service' in monitor and '--follow' in monitor
assert (op/'show/console-server/ports/node.def').is_file()
libs=list((r/'usr/local/lib/vyos-kvm-media').glob('librockchip_mpp.so*'))
assert libs, 'MPP libraries missing'
for lib in libs:
 st=lib.lstat();assert (st.st_uid,st.st_gid)==(0,0),(lib,st)
for kind in ['native-cli','kvm-cli']:
 st=(r/f'usr/share/vyos-arm64-board-builder/{kind}/build.json').stat()
 assert (st.st_uid,st.st_gid,st.st_mode & 0o777)==(0,0,0o644),(kind,st)
print('CLI, runtime, host fixes, A-D/F profile metadata and absence of SSH private host keys verified')
PY
mkdir -p "$V/root/run"
mount -t tmpfs tmpfs "$V/root/run"
cat > "$V/root/run/verify-schema.py" <<'PY'
from vyos.configtree import ConfigTree,validate_tree
from vyos.xml_ref import owner
c=ConfigTree('')
for path,value in [(['container','name','kiosk','kiosk','display-backend'],'wayland'),(['container','name','kiosk','kiosk','video-decode'],'auto'),(['container','name','kiosk','kiosk','video-h264-buffers'],'enabled'),(['container','name','kiosk','kiosk','video-av1-buffers'],'enabled')]:
    c.set(path,value=value)
c.set_tag(['container','name'])
assert not validate_tree(c)
assert owner(['container','name','kiosk','kiosk','display-backend'],with_tag=True)=='container'
assert owner(['service','kvm-over-ip','local-input','keyboard'],with_tag=True)=='service_kvm_over_ip'
print('Native D/F command ownership and Wayland/decoder configuration schema verified')
PY
chroot "$V/root" python3 /run/verify-schema.py
lsinitramfs "$SD/initrd.img" > "$V/initrd-files.txt"
grep -q 'arm/mali/arch10.8/mali_csffw.bin' "$V/initrd-files.txt"
chown -R 1000:1000 /work/output
printf 'FULL_ARTIFACT_VERIFICATION_OK\n' | tee /work/verification-complete
