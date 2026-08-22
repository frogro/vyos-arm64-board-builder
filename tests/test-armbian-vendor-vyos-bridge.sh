#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRIDGE="$ROOT/tools/firmware-providers/armbian-uboot/bootfiles.sh"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

EFI="$WORK/efi"
VERSION="1.5-rolling-202608170807"
VERSION_DIR="$WORK/persistence/boot/$VERSION"
GRUB_CFG="$WORK/$VERSION.cfg"
MANIFEST="$WORK/boot-manifest.env"

mkdir -p "$EFI" "$VERSION_DIR/dtb/rockchip"

printf 'kernel\n' > "$VERSION_DIR/vmlinuz"
printf 'initrd\n' > "$VERSION_DIR/initrd.img"
printf 'dtb\n' > "$VERSION_DIR/dtb/rockchip/rk3582-radxa-e52c.dtb"

cat > "$GRUB_CFG" <<EOF
menuentry "$VERSION" {
    set boot_opts="boot=live rootdelay=5 noautologin net.ifnames=0 biosdevname=0 vyos-union=/boot/$VERSION"
    linux "/boot/$VERSION/vmlinuz" \${boot_opts}
    initrd "/boot/$VERSION/initrd.img"
}
EOF

cat > "$MANIFEST" <<'EOF'
BOARD=radxa-e52c
BOARD_NAME='Radxa E52C'
BOARD_FAMILY=rockchip-rk3588
FIRMWARE_PROVIDER=armbian-uboot
HW_BRANCH=current
BOOT_BRANCH=vendor
BOOT_FDT_FILE=rockchip/rk3582-radxa-e52c.dtb
HW_DEFAULT_CONSOLE=serial
HW_SERIALCON=ttyS2
UBOOT_BOOTSCRIPT=boot-rk35xx.cmd:boot.cmd
EOF

"$BRIDGE" radxa-e52c "$EFI" "$VERSION_DIR" "$GRUB_CFG" "$MANIFEST"

test -s "$EFI/vyos-boot/Image"
test -s "$EFI/vyos-boot/initrd.img"
test -s "$EFI/vyos-boot/dtb/rockchip/rk3582-radxa-e52c.dtb"
cmp "$VERSION_DIR/vmlinuz" "$EFI/vyos-boot/Image"
cmp "$VERSION_DIR/initrd.img" "$EFI/vyos-boot/initrd.img"
cmp "$VERSION_DIR/dtb/rockchip/rk3582-radxa-e52c.dtb" "$EFI/vyos-boot/dtb/rockchip/rk3582-radxa-e52c.dtb"

grep -Fq "boot=live rootdelay=5 noautologin net.ifnames=0 biosdevname=0 vyos-union=/boot/$VERSION" "$EFI/extlinux/extlinux.conf"
grep -Fq "console=ttyS2,1500000n8" "$EFI/extlinux/extlinux.conf"
grep -Fq "FDT /vyos-boot/dtb/rockchip/rk3582-radxa-e52c.dtb" "$EFI/extlinux/extlinux.conf"
cmp "$EFI/extlinux/extlinux.conf" "$EFI/boot/extlinux/extlinux.conf"

SKIP_EFI="$WORK/skip-efi"
SKIP_MANIFEST="$WORK/skip-manifest.env"
mkdir -p "$SKIP_EFI"
sed 's/^BOOT_BRANCH=vendor$/BOOT_BRANCH=current/' "$MANIFEST" > "$SKIP_MANIFEST"

"$BRIDGE" radxa-e52c "$SKIP_EFI" "$VERSION_DIR" "$GRUB_CFG" "$SKIP_MANIFEST"

test ! -e "$SKIP_EFI/extlinux/extlinux.conf"
test ! -e "$SKIP_EFI/vyos-boot/Image"

echo "PASS: Armbian vendor-current VyOS boot bridge"
