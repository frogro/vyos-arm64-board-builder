#!/usr/bin/env bash
set -euo pipefail

BOARD="${1:?Usage: $0 <board> <efi-root> <version-dir> <grub-version-cfg> <boot-manifest>}"
EFI_ROOT="${2:?Usage: $0 <board> <efi-root> <version-dir> <grub-version-cfg> <boot-manifest>}"
VERSION_DIR="${3:?Usage: $0 <board> <efi-root> <version-dir> <grub-version-cfg> <boot-manifest>}"
GRUB_VERSION_CFG="${4:?Usage: $0 <board> <efi-root> <version-dir> <grub-version-cfg> <boot-manifest>}"
MANIFEST="${5:?Usage: $0 <board> <efi-root> <version-dir> <grub-version-cfg> <boot-manifest>}"

[[ -d "$EFI_ROOT" ]] || { echo "ERROR: EFI root missing: $EFI_ROOT" >&2; exit 1; }
[[ -d "$VERSION_DIR" ]] || { echo "ERROR: VyOS version directory missing: $VERSION_DIR" >&2; exit 1; }
[[ -s "$GRUB_VERSION_CFG" ]] || { echo "ERROR: VyOS GRUB version config missing: $GRUB_VERSION_CFG" >&2; exit 1; }
[[ -s "$MANIFEST" ]] || { echo "ERROR: boot manifest missing: $MANIFEST" >&2; exit 1; }

# shellcheck disable=SC1090
source "$MANIFEST"

if [[ "${FIRMWARE_PROVIDER:-}" != "armbian-uboot" ]]; then
    echo "Armbian vendor-current VyOS bridge skipped: provider=${FIRMWARE_PROVIDER:-unset}"
    exit 0
fi

if [[ "${BOOT_BRANCH:-}" != "vendor" || "${HW_BRANCH:-}" != "current" ]]; then
    echo "Armbian vendor-current VyOS bridge skipped: hw=${HW_BRANCH:-unset} boot=${BOOT_BRANCH:-unset}"
    exit 0
fi

case "${UBOOT_BOOTSCRIPT:-}" in
    boot-rk35xx.cmd|boot-rk35xx.cmd:*)
        ;;
    *)
        echo "Armbian vendor-current VyOS bridge skipped: bootscript=${UBOOT_BOOTSCRIPT:-unset}"
        exit 0
        ;;
esac

: "${BOOT_FDT_FILE:?BOOT_FDT_FILE missing from boot manifest}"

VERSION="$(basename "$VERSION_DIR")"
KERNEL="$VERSION_DIR/vmlinuz"
INITRD="$VERSION_DIR/initrd.img"
DTB="$VERSION_DIR/dtb/$BOOT_FDT_FILE"

for required in "$KERNEL" "$INITRD" "$DTB"; do
    [[ -s "$required" ]] || { echo "ERROR: vendor-current boot payload missing: $required" >&2; exit 1; }
done

BOOT_OPTS="$(
    sed -n 's/^[[:space:]]*set boot_opts="\([^"]*\)".*$/\1/p' "$GRUB_VERSION_CFG" |
    head -1
)"
[[ -n "$BOOT_OPTS" ]] || { echo "ERROR: unable to derive VyOS boot options from $GRUB_VERSION_CFG" >&2; exit 1; }

SERIAL_BAUD="${VYOS_VENDOR_BOOT_BAUD:-1500000}"

case "${HW_DEFAULT_CONSOLE:-}" in
    serial)
        : "${HW_SERIALCON:?serial board has no HW_SERIALCON in boot manifest}"
        CONSOLE_OPTS="console=${HW_SERIALCON},${SERIAL_BAUD}n8"
        ;;
    both)
        : "${HW_SERIALCON:?both-console board has no HW_SERIALCON in boot manifest}"
        CONSOLE_OPTS="console=${HW_SERIALCON},${SERIAL_BAUD}n8 console=tty1"
        ;;
    display)
        CONSOLE_OPTS="console=tty1"
        ;;
    *)
        if [[ -n "${HW_SERIALCON:-}" ]]; then
            CONSOLE_OPTS="console=${HW_SERIALCON},${SERIAL_BAUD}n8"
        else
            CONSOLE_OPTS="console=tty1"
        fi
        ;;
esac

PAYLOAD="$EFI_ROOT/vyos-boot"
EXTLINUX_ROOT="$EFI_ROOT/extlinux/extlinux.conf"
EXTLINUX_BOOT="$EFI_ROOT/boot/extlinux/extlinux.conf"

rm -rf "$PAYLOAD"
mkdir -p \
    "$PAYLOAD/dtb/$(dirname "$BOOT_FDT_FILE")" \
    "$(dirname "$EXTLINUX_ROOT")" \
    "$(dirname "$EXTLINUX_BOOT")"

install -m 0644 "$KERNEL" "$PAYLOAD/Image"
install -m 0644 "$INITRD" "$PAYLOAD/initrd.img"
install -m 0644 "$DTB" "$PAYLOAD/dtb/$BOOT_FDT_FILE"

cat > "$PAYLOAD/bridge.env" <<EOF
SCHEMA=1
BOARD=$BOARD
VERSION=$VERSION
FIRMWARE_PROVIDER=$FIRMWARE_PROVIDER
HW_BRANCH=$HW_BRANCH
BOOT_BRANCH=$BOOT_BRANCH
BOOT_FDT_FILE=$BOOT_FDT_FILE
HW_DEFAULT_CONSOLE=${HW_DEFAULT_CONSOLE:-}
HW_SERIALCON=${HW_SERIALCON:-}
SERIAL_BAUD=$SERIAL_BAUD
UBOOT_BOOTSCRIPT=${UBOOT_BOOTSCRIPT:-}
EOF

cat > "$EXTLINUX_ROOT" <<EOF
DEFAULT vyos
TIMEOUT 10
MENU TITLE VyOS ARM64 vendor U-Boot bridge

LABEL vyos
    MENU LABEL VyOS $VERSION
    LINUX /vyos-boot/Image
    INITRD /vyos-boot/initrd.img
    FDT /vyos-boot/dtb/$BOOT_FDT_FILE
    APPEND $BOOT_OPTS $CONSOLE_OPTS
EOF

cp "$EXTLINUX_ROOT" "$EXTLINUX_BOOT"

grep -Fq "LINUX /vyos-boot/Image" "$EXTLINUX_ROOT"
grep -Fq "INITRD /vyos-boot/initrd.img" "$EXTLINUX_ROOT"
grep -Fq "FDT /vyos-boot/dtb/$BOOT_FDT_FILE" "$EXTLINUX_ROOT"
grep -Fq "vyos-union=/boot/$VERSION" "$EXTLINUX_ROOT"

echo "Installed Armbian vendor-current VyOS boot bridge"
echo "  Board:       $BOARD"
echo "  Version:     $VERSION"
echo "  Kernel:      /vyos-boot/Image"
echo "  Initrd:      /vyos-boot/initrd.img"
echo "  DTB:         /vyos-boot/dtb/$BOOT_FDT_FILE"
echo "  Console:     $CONSOLE_OPTS"
echo "  Extlinux:    /extlinux/extlinux.conf"
echo "  Fallback:    /boot/extlinux/extlinux.conf"
