#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

mkdir -p \
    "$WORK/firmware" \
    "$WORK/version" \
    "$WORK/artifacts/dtb/broadcom"

cat > "$WORK/firmware/config.txt" <<'EOF_CONFIG'
[pi5]
arm_64bit=1
EOF_CONFIG

cat > "$WORK/grub-version.cfg" <<'EOF_GRUB'
menuentry "test" {
    set boot_opts="boot=live rootdelay=5 noautologin net.ifnames=0 biosdevname=0 vyos-union=/boot/2026.08.19-test"
    linux "/boot/2026.08.19-test/vmlinuz" ${boot_opts}
    initrd "/boot/2026.08.19-test/initrd.img"
}
EOF_GRUB

printf 'kernel-payload\n' > "$WORK/artifacts/Image"
printf 'initrd-payload\n' > "$WORK/version/initrd.img"
printf 'dtb-payload\n' > "$WORK/artifacts/dtb/broadcom/bcm2712-rpi-5-b.dtb"

BOOT_FDT_FILE=broadcom/bcm2712-rpi-5-b.dtb \
    "$ROOT/tools/firmware-providers/raspberrypi-native/finalize.sh" \
        raspberry-pi-5 \
        "$WORK/firmware" \
        "$WORK/version" \
        "$WORK/artifacts" \
        "$WORK/grub-version.cfg"

grep -Eq '^\[all\]$' "$WORK/firmware/config.txt"
grep -Eq '^kernel=vmlinuz$' "$WORK/firmware/config.txt"
grep -Eq '^initramfs initrd\.img followkernel$' "$WORK/firmware/config.txt"
grep -Eq '^device_tree=bcm2712-rpi-5-b\.dtb$' "$WORK/firmware/config.txt"
grep -Eq '(^| )boot=live( |$)' "$WORK/firmware/cmdline.txt"
grep -Eq '(^| )vyos-union=/boot/2026\.08\.19-test( |$)' "$WORK/firmware/cmdline.txt"
grep -Eq '(^| )console=ttyAMA10,115200( |$)' "$WORK/firmware/cmdline.txt"
cmp -s "$WORK/artifacts/Image" "$WORK/firmware/vmlinuz"
cmp -s "$WORK/version/initrd.img" "$WORK/firmware/initrd.img"

echo "PASS: raspberrypi-native finalize contract"
