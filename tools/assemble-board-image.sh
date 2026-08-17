#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BOARD="${1:?Usage: $0 <board> <branch> <vyos.raw> [output.img]}"
BRANCH="${2:?Usage: $0 <board> <branch> <vyos.raw> [output.img]}"
RAW="${3:?Usage: $0 <board> <branch> <vyos.raw> [output.img]}"
OUTPUT="${4:-$ROOT/work/build/$BOARD/vyos-${BOARD}.img}"

BOOT="$ROOT/work/build/$BOARD/boot"
BOOT_ARTIFACTS="$BOOT/artifacts"
BOOT_METADATA="$BOOT/metadata"
KERNEL_ARTIFACTS="$ROOT/work/build/$BOARD/artifacts"
MODULES_ROOT="$ROOT/work/build/$BOARD/modules"

BOOT_GAP_MIB="${BOOT_GAP_MIB:-32}"
SECTOR_SIZE=512
ALIGN_SECTORS=2048

die()
{
    echo "ERROR: $*" >&2
    exit 1
}

need()
{
    command -v "$1" >/dev/null 2>&1 ||
        die "required command not found: $1"
}

for cmd in \
    losetup \
    sgdisk \
    blkid \
    blockdev \
    rsync \
    unsquashfs \
    mksquashfs \
    depmod \
    python3 \
    dd
do
    need "$cmd"
done

[[ $EUID -eq 0 ]] ||
    die "assemble-board-image.sh must run as root"

[[ -f "$RAW" ]] ||
    die "VyOS raw image not found: $RAW"

[[ -s "$KERNEL_ARTIFACTS/Image" ]] ||
    die "board kernel Image missing"

[[ -s "$KERNEL_ARTIFACTS/kernel.release" ]] ||
    die "kernel.release missing"

[[ -d "$MODULES_ROOT/lib/modules" ]] ||
    die "board kernel modules missing"

PLATFORM_INSTALL="$BOOT_METADATA/platform_install.sh"

[[ -f "$PLATFORM_INSTALL" ]] ||
    die "Armbian platform_install.sh missing"

[[ -d "$BOOT_ARTIFACTS" ]] ||
    die "bootchain artifacts missing"

MANIFEST="$BOOT/boot-manifest.env"

[[ -f "$MANIFEST" ]] ||
    die "boot manifest missing"

# shellcheck disable=SC1090
source "$MANIFEST"

[[ -n "${BOOT_FDT_FILE:-}" ]] ||
    die "BOOT_FDT_FILE missing from boot manifest"

DTB="$KERNEL_ARTIFACTS/dtb/$BOOT_FDT_FILE"

[[ -s "$DTB" ]] ||
    die "board DTB missing: $DTB"

KERNEL_RELEASE="$(cat "$KERNEL_ARTIFACTS/kernel.release")"

echo "===== ASSEMBLY INPUT ====="
echo "Board:          $BOARD"
echo "Branch:         $BRANCH"
echo "VyOS RAW:       $RAW"
echo "Kernel release: $KERNEL_RELEASE"
echo "DTB:            $BOOT_FDT_FILE"
echo "Boot gap:       ${BOOT_GAP_MIB} MiB"
echo

mkdir -p "$(dirname "$OUTPUT")"

WORK="$(mktemp -d)"
SRC_MNT="$WORK/src"
DST_MNT="$WORK/dst"
SQUASH_ROOT="$WORK/squash-root"

mkdir -p "$SRC_MNT" "$DST_MNT"

SRC_LOOP=""
DST_LOOP=""

cleanup()
{
    set +e

    mountpoint -q "$DST_MNT/boot/efi" &&
        umount "$DST_MNT/boot/efi"

    mountpoint -q "$DST_MNT" &&
        umount "$DST_MNT"

    [[ -n "$DST_LOOP" ]] &&
        losetup -d "$DST_LOOP" 2>/dev/null

    [[ -n "$SRC_LOOP" ]] &&
        losetup -d "$SRC_LOOP" 2>/dev/null

    rm -rf "$WORK"
}

trap cleanup EXIT

SRC_LOOP="$(
    losetup \
        --find \
        --show \
        --partscan \
        "$RAW"
)"

udevadm settle

EFI_SRC=""
ROOT_SRC=""

for part in "${SRC_LOOP}"p*; do
    [[ -b "$part" ]] || continue

    label="$(blkid -s LABEL -o value "$part" 2>/dev/null || true)"
    type="$(blkid -s TYPE -o value "$part" 2>/dev/null || true)"

    if [[ "$label" == "EFI" && "$type" == "vfat" ]]; then
        EFI_SRC="$part"
    fi

    if [[ "$label" == "persistence" && "$type" == "ext4" ]]; then
        ROOT_SRC="$part"
    fi
done

[[ -n "$EFI_SRC" ]] ||
    die "Unable to locate VyOS EFI partition"

[[ -n "$ROOT_SRC" ]] ||
    die "Unable to locate VyOS persistence partition"

EFI_SECTORS="$(blockdev --getsz "$EFI_SRC")"
ROOT_SECTORS="$(blockdev --getsz "$ROOT_SRC")"

BOOT_GAP_SECTORS="$((BOOT_GAP_MIB * 1024 * 1024 / SECTOR_SIZE))"

align_up()
{
    local value="$1"
    local align="$2"

    echo $(( ((value + align - 1) / align) * align ))
}

EFI_START="$(align_up "$BOOT_GAP_SECTORS" "$ALIGN_SECTORS")"
EFI_END="$((EFI_START + EFI_SECTORS - 1))"

ROOT_START="$(align_up $((EFI_END + 1)) "$ALIGN_SECTORS")"
ROOT_END="$((ROOT_START + ROOT_SECTORS - 1))"

TOTAL_SECTORS="$((ROOT_END + ALIGN_SECTORS + 34))"
TOTAL_BYTES="$((TOTAL_SECTORS * SECTOR_SIZE))"

rm -f "$OUTPUT"
truncate -s "$TOTAL_BYTES" "$OUTPUT"

sgdisk --zap-all "$OUTPUT"
sgdisk --clear "$OUTPUT"

sgdisk \
    --new=1:${EFI_START}:${EFI_END} \
    --typecode=1:ef00 \
    --change-name=1:EFI \
    "$OUTPUT"

sgdisk \
    --new=2:${ROOT_START}:${ROOT_END} \
    --typecode=2:8300 \
    --change-name=2:persistence \
    "$OUTPUT"

sgdisk --print "$OUTPUT"

DST_LOOP="$(
    losetup \
        --find \
        --show \
        --partscan \
        "$OUTPUT"
)"

udevadm settle

EFI_DST="${DST_LOOP}p1"
ROOT_DST="${DST_LOOP}p2"

[[ -b "$EFI_DST" ]] ||
    die "target EFI partition missing"

[[ -b "$ROOT_DST" ]] ||
    die "target persistence partition missing"

echo
echo "===== COPYING VYOS FILESYSTEMS ====="

dd \
    if="$EFI_SRC" \
    of="$EFI_DST" \
    bs=4M \
    conv=fsync \
    status=progress

dd \
    if="$ROOT_SRC" \
    of="$ROOT_DST" \
    bs=4M \
    conv=fsync \
    status=progress

mount "$ROOT_DST" "$DST_MNT"

mkdir -p "$DST_MNT/boot/efi"
mount "$EFI_DST" "$DST_MNT/boot/efi"

VERSION_DIR="$(
    find "$DST_MNT/boot" \
        -mindepth 1 \
        -maxdepth 1 \
        -type d \
        -exec test -f '{}/vmlinuz' ';' \
        -print \
        -quit
)"

[[ -n "$VERSION_DIR" ]] ||
    die "VyOS version directory not found"

VERSION="$(basename "$VERSION_DIR")"

EXPECTED_KERNEL_RELEASE="$(
    find "$VERSION_DIR" \
        -maxdepth 1 \
        -type f \
        -name 'vmlinuz-*' \
        -printf '%f\n' |
        sed 's/^vmlinuz-//' |
        head -1
)"

[[ -n "$EXPECTED_KERNEL_RELEASE" ]] ||
    die "Unable to determine kernel release expected by VyOS image"

echo
echo "VyOS version:            $VERSION"
echo "VyOS expected kernel:    $EXPECTED_KERNEL_RELEASE"
echo "Board kernel release:    $KERNEL_RELEASE"

[[ "$KERNEL_RELEASE" == "$EXPECTED_KERNEL_RELEASE" ]] ||
    die "Kernel ABI mismatch: board=${KERNEL_RELEASE}, VyOS=${EXPECTED_KERNEL_RELEASE}"

MODULE_SOURCE="$MODULES_ROOT/lib/modules/$KERNEL_RELEASE"

[[ -d "$MODULE_SOURCE" ]] ||
    die "module tree missing: $MODULE_SOURCE"

echo
echo "===== INSTALLING BOARD KERNEL ====="

cp "$KERNEL_ARTIFACTS/Image" \
    "$VERSION_DIR/vmlinuz"

cp "$KERNEL_ARTIFACTS/Image" \
    "$VERSION_DIR/vmlinuz-$KERNEL_RELEASE"

DTB_TARGET="$VERSION_DIR/dtb/$BOOT_FDT_FILE"

mkdir -p "$(dirname "$DTB_TARGET")"
cp "$DTB" "$DTB_TARGET"

echo
echo "===== INSTALLING BOARD MODULES INTO VYOS SQUASHFS ====="

SQUASH="$(
    find "$VERSION_DIR" \
        -maxdepth 1 \
        -type f \
        -name '*.squashfs' \
        -print \
        -quit
)"

[[ -n "$SQUASH" ]] ||
    die "VyOS squashfs not found"

rm -rf "$SQUASH_ROOT"

unsquashfs \
    -d "$SQUASH_ROOT" \
    "$SQUASH"

rm -rf "$SQUASH_ROOT/lib/modules/$KERNEL_RELEASE"

mkdir -p "$SQUASH_ROOT/lib/modules/$KERNEL_RELEASE"

rsync \
    -aHAX \
    "$MODULE_SOURCE/" \
    "$SQUASH_ROOT/lib/modules/$KERNEL_RELEASE/"

depmod \
    -b "$SQUASH_ROOT" \
    "$KERNEL_RELEASE"

NEW_SQUASH="$WORK/new.squashfs"

mksquashfs \
    "$SQUASH_ROOT" \
    "$NEW_SQUASH" \
    -comp xz \
    -b 256K \
    -always-use-fragments \
    -no-recovery \
    -noappend

mv "$NEW_SQUASH" "$SQUASH"

echo
echo "===== ADDING BOARD DTB TO GRUB ====="

GRUB_VERSION_CFG="$(
    find "$DST_MNT/boot/grub" \
        -type f \
        -path '*/vyos-versions/*.cfg' \
        -name "${VERSION}.cfg" \
        -print \
        -quit
)"

[[ -n "$GRUB_VERSION_CFG" ]] ||
    die "VyOS GRUB version config not found"

python3 - \
    "$GRUB_VERSION_CFG" \
    "$VERSION" \
    "$BOOT_FDT_FILE" <<'PY'
from pathlib import Path
import sys

cfg = Path(sys.argv[1])
version = sys.argv[2]
dtb = sys.argv[3]

text = cfg.read_text()

linux_line = f'    linux "/boot/{version}/vmlinuz"'

if linux_line not in text:
    raise SystemExit("ERROR: expected VyOS GRUB linux line not found")

dtb_line = f'    devicetree "/boot/{version}/dtb/{dtb}"'

if dtb_line not in text:
    text = text.replace(
        linux_line,
        dtb_line + "\n" + linux_line,
        1
    )

cfg.write_text(text)

print(f"Added GRUB devicetree: /boot/{version}/dtb/{dtb}")
PY

sync

umount "$DST_MNT/boot/efi"
umount "$DST_MNT"

losetup -d "$DST_LOOP"
DST_LOOP=""

losetup -d "$SRC_LOOP"
SRC_LOOP=""

echo
echo "===== INSTALLING ARMBIAN-DERIVED BOARD BOOTCHAIN ====="

# shellcheck disable=SC1090
source "$PLATFORM_INSTALL"

declare -F write_uboot_platform >/dev/null ||
    die "write_uboot_platform() not supplied by Armbian package"

write_uboot_platform \
    "$BOOT_ARTIFACTS" \
    "$OUTPUT"

sync

echo
echo "===== FINAL IMAGE VALIDATION ====="

sgdisk --verify "$OUTPUT"
sgdisk --print "$OUTPUT"

CHECK_LOOP="$(
    losetup \
        --find \
        --show \
        --partscan \
        "$OUTPUT"
)"

udevadm settle

fsck.vfat -n "${CHECK_LOOP}p1"
e2fsck -fn "${CHECK_LOOP}p2"

losetup -d "$CHECK_LOOP"

echo
echo "===== FINAL IMAGE ====="
ls -lh "$OUTPUT"

echo
echo "Board image assembled successfully:"
echo "  $OUTPUT"
