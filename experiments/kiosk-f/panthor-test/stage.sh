#!/bin/bash
# Called only from explicitly opted-in test image assembly.
set -euo pipefail
ROOT=${1:?offline root}; INPUT=${2:?artifacts}
[[ "$ROOT" != / && -d "$ROOT/usr" ]]
HERE=$(cd "$(dirname "$0")" && pwd)
(cd "$INPUT" && sha256sum -c SHA256SUMS)
KREL=$(cat "$INPUT/kernel.release")
[[ "$KREL" == 6.18.50-vyos-panthor-cache-test ]]
[[ ! -e "$ROOT/usr/lib/modules/$KREL" ]]
tar -xf "$INPUT/modules.tar" -C "$ROOT/usr" lib/modules
chown -R 0:0 "$ROOT/usr/lib/modules/$KREL"
cp "$INPUT/kernel.config" "$ROOT/boot/config-$KREL"
cp "$INPUT/System.map" "$ROOT/boot/System.map-$KREL"
chroot "$ROOT" /usr/sbin/depmod "$KREL"
chroot "$ROOT" /usr/sbin/update-initramfs -c -k "$KREL"
P="$ROOT/usr/share/vyarm/panthor-test"
mkdir -p "$P" "$ROOT/usr/local/libexec" "$ROOT/etc/systemd/system/multi-user.target.wants"
cp "$INPUT/Image" "$INPUT/board.dtb" "$INPUT/kernel.release" "$P/"
cp "$ROOT/boot/initrd.img-$KREL" "$P/initrd.img"
cp "$HERE/install-menu.py" "$ROOT/usr/local/libexec/vyarm-panthor-test-menu"
chmod 755 "$ROOT/usr/local/libexec/vyarm-panthor-test-menu"
cat > "$ROOT/etc/systemd/system/vyarm-panthor-test-menu.service" <<'UNIT'
[Unit]
Description=Prepare optional Panthor test boot entry (normal default retained)
After=vyos-router.service
ConditionPathExists=/usr/share/vyarm/panthor-test/Image
[Service]
Type=oneshot
TimeoutStartSec=150
ExecStart=/usr/local/libexec/vyarm-panthor-test-menu
[Install]
WantedBy=multi-user.target
UNIT
ln -s ../vyarm-panthor-test-menu.service "$ROOT/etc/systemd/system/multi-user.target.wants/vyarm-panthor-test-menu.service"
lsinitramfs "$P/initrd.img" > "$INPUT/initrd-files.txt"
grep -q "lib/modules/$KREL/" "$INPUT/initrd-files.txt"
grep -q 'arm/mali/arch10.8/mali_csffw.bin' "$INPUT/initrd-files.txt"
for module in overlay squashfs; do
    grep -Eq "/$module\.ko(\.|$)" "$INPUT/initrd-files.txt"
done
