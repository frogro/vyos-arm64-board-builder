#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BOARD="${1:?Usage: $0 <board> <branch> <vyos.raw> [output.img]}"
BRANCH="${2:?Usage: $0 <board> <branch> <vyos.raw> [output.img]}"
RAW="${3:?Usage: $0 <board> <branch> <vyos.raw> [output.img]}"
OUTPUT="${4:-$ROOT/work/build/$BOARD/vyos-${BOARD}.img}"

KERNEL_ARTIFACTS="$ROOT/work/build/$BOARD/artifacts"
MODULES_ROOT="$ROOT/work/build/$BOARD/modules"
BOOT="$ROOT/work/build/$BOARD/boot"
MANIFEST="$BOOT/boot-manifest.env"
NETWORK_ARTIFACTS="$KERNEL_ARTIFACTS/network-firmware"
NETWORK_SELECTION="$ROOT/work/build/$BOARD/selection/extended-network.env"
FEATURE_SELECTION="$ROOT/work/build/$BOARD/selection/feature-profiles.env"

EXTENDED_NETWORK="${EXTENDED_NETWORK:-no}"
TAILSCALE_SUBNET_ROUTER="${TAILSCALE_SUBNET_ROUTER:-no}"
BUILD_PROFILE="${BUILD_PROFILE:-base}"
KVM_OVER_IP="${KVM_OVER_IP:-no}"
if [[ -f "$NETWORK_SELECTION" ]]; then
    # shellcheck disable=SC1090
    source "$NETWORK_SELECTION"
fi
if [[ -f "$FEATURE_SELECTION" ]]; then
    # shellcheck disable=SC1090
    source "$FEATURE_SELECTION"
fi

SECTOR_SIZE=512

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
    udevadm \
    sgdisk \
    blkid \
    blockdev \
    rsync \
    unsquashfs \
    mksquashfs \
    depmod \
    lsinitramfs \
    python3 \
    dd \
    mount \
    umount \
    mountpoint \
    fsck.vfat \
    e2fsck \
    sha256sum \
    strings \
    stat \
    cmp \
    chroot \
    truncate \
    find \
    grep
do
    need "$cmd"
done

[[ $EUID -eq 0 ]] ||
    die "assemble-board-image.sh must run as root"

[[ "$(uname -m)" == "aarch64" ]] ||
    die "final VyOS initramfs generation currently requires a native ARM64 runner"

[[ -f "$RAW" ]] ||
    die "VyOS raw image not found: $RAW"

[[ -s "$KERNEL_ARTIFACTS/Image" ]] ||
    die "board kernel Image missing"

[[ -s "$KERNEL_ARTIFACTS/kernel.release" ]] ||
    die "kernel.release missing"

[[ -s "$KERNEL_ARTIFACTS/kernel.config" ]] ||
    die "final kernel.config missing"

[[ -s "$KERNEL_ARTIFACTS/System.map" ]] ||
    die "final System.map missing"

[[ -d "$MODULES_ROOT/lib/modules" ]] ||
    die "board kernel modules missing"

[[ -f "$MANIFEST" ]] ||
    die "boot manifest missing"

# shellcheck disable=SC1090
source "$MANIFEST"

[[ -n "${BOOT_FDT_FILE:-}" ]] ||
    die "BOOT_FDT_FILE missing from boot manifest"

[[ -n "${FIRMWARE_PROVIDER:-}" ]] ||
    die "FIRMWARE_PROVIDER missing from boot manifest"

[[ -n "${FIRMWARE_LAYOUT_MODE:-}" ]] ||
    die "FIRMWARE_LAYOUT_MODE missing from boot manifest"

[[ "${PARTITION_TABLE:-gpt}" == "gpt" ]] ||
    die "current VyOS board-image assembler requires GPT"

for value_name in     FIRMWARE_PART_START     FIRMWARE_PART_SECTORS     EFI_START_SECTOR
do
    value="${!value_name:-}"

    [[ "$value" =~ ^[0-9]+$ ]] ||
        die "$value_name must be an integer sector count"
done

FIRMWARE_PART_END=$((FIRMWARE_PART_START + FIRMWARE_PART_SECTORS - 1))

(( FIRMWARE_PART_END + 1 == EFI_START_SECTOR )) ||
    die "firmware layout is not contiguous with EFI start"

INSTALL_PROVIDER="$ROOT/tools/firmware-providers/$FIRMWARE_PROVIDER/install.sh"
ROOTFS_PROVIDER="$ROOT/tools/firmware-providers/$FIRMWARE_PROVIDER/rootfs.sh"
FINALIZE_PROVIDER="$ROOT/tools/firmware-providers/$FIRMWARE_PROVIDER/finalize.sh"
VALIDATE_PROVIDER="$ROOT/tools/firmware-providers/$FIRMWARE_PROVIDER/validate.sh"
COMMON_ROOTFS_FINALIZER="$ROOT/tools/finalize-vyos-rootfs.sh"
ARM_CPU_OPMODE_PATCHER="$ROOT/tools/patch-vyos-arm-cpu-opmode.py"
GRUB_CONSOLE_TOOL="$ROOT/tools/set-grub-console-default.py"

[[ -x "$INSTALL_PROVIDER" ]] ||
    die "firmware provider installer missing: $INSTALL_PROVIDER"

[[ -x "$COMMON_ROOTFS_FINALIZER" ]] ||
    die "common VyOS rootfs finalizer missing: $COMMON_ROOTFS_FINALIZER"

[[ -x "$ARM_CPU_OPMODE_PATCHER" ]] ||
    die "VyOS ARM CPU op-mode patcher missing: $ARM_CPU_OPMODE_PATCHER"

[[ -x "$GRUB_CONSOLE_TOOL" ]] ||
    die "GRUB console-default tool missing: $GRUB_CONSOLE_TOOL"

DTB="$KERNEL_ARTIFACTS/dtb/$BOOT_FDT_FILE"

[[ -s "$DTB" ]] ||
    die "board DTB missing: $DTB"

KERNEL_RELEASE="$(cat "$KERNEL_ARTIFACTS/kernel.release")"

echo "===== ASSEMBLY INPUT ====="
echo "Board:             $BOARD"
echo "Branch:            $BRANCH"
echo "VyOS RAW:          $RAW"
echo "Kernel release:    $KERNEL_RELEASE"
echo "DTB:               $BOOT_FDT_FILE"
echo "Firmware provider: $FIRMWARE_PROVIDER"
echo "Firmware layout:   $FIRMWARE_LAYOUT_MODE"
echo "Firmware GPT1:     ${FIRMWARE_PART_START}-${FIRMWARE_PART_END}"
echo "EFI start sector:  $EFI_START_SECTOR"
echo

mkdir -p "$(dirname "$OUTPUT")"

WORK="$(mktemp -d)"
SRC_MNT="$WORK/src"
DST_MNT="$WORK/dst"
SQUASH_ROOT="$WORK/squash-root"
FIRMWARE_MNT="$WORK/firmware"

mkdir -p "$SRC_MNT" "$DST_MNT" "$FIRMWARE_MNT"

SRC_LOOP=""
DST_LOOP=""

unmount_chroot()
{
    mountpoint -q "$SQUASH_ROOT/run" &&
        umount "$SQUASH_ROOT/run" || true
    mountpoint -q "$SQUASH_ROOT/sys" &&
        umount "$SQUASH_ROOT/sys" || true
    mountpoint -q "$SQUASH_ROOT/proc" &&
        umount "$SQUASH_ROOT/proc" || true
    mountpoint -q "$SQUASH_ROOT/dev/pts" &&
        umount "$SQUASH_ROOT/dev/pts" || true
    mountpoint -q "$SQUASH_ROOT/dev" &&
        umount "$SQUASH_ROOT/dev" || true
}

cleanup()
{
    set +e

    unmount_chroot

    mountpoint -q "$FIRMWARE_MNT" &&
        umount "$FIRMWARE_MNT"

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
        --read-only \
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
RAW_BYTES="$(stat -c '%s' "$RAW")"
RAW_SECTORS=$((RAW_BYTES / SECTOR_SIZE))
OUTPUT_EXTRA_SECTORS="${OUTPUT_EXTRA_SECTORS:-0}"

[[ "$OUTPUT_EXTRA_SECTORS" =~ ^[0-9]+$ ]] ||
    die "OUTPUT_EXTRA_SECTORS must be an integer"

OUTPUT_SECTORS=$((RAW_SECTORS + OUTPUT_EXTRA_SECTORS))
OUTPUT_BYTES=$((OUTPUT_SECTORS * SECTOR_SIZE))

EFI_START="$EFI_START_SECTOR"
EFI_END=$((EFI_START + EFI_SECTORS - 1))
ROOT_START=$((EFI_END + 1))
ROOT_END=$((ROOT_START + ROOT_SECTORS - 1))

(( ROOT_END + 34 < OUTPUT_SECTORS )) ||
    die "VyOS filesystems do not fit in the provider-defined layout"

rm -f "$OUTPUT"
truncate -s "$OUTPUT_BYTES" "$OUTPUT"

sgdisk --zap-all "$OUTPUT"
sgdisk --clear "$OUTPUT"

sgdisk \
    --new=1:${FIRMWARE_PART_START}:${FIRMWARE_PART_END} \
    --typecode=1:${FIRMWARE_PART_TYPE:-8300} \
    --change-name=1:${FIRMWARE_PART_NAME:-uboot} \
    "$OUTPUT"

sgdisk \
    --new=2:${EFI_START}:${EFI_END} \
    --typecode=2:ef00 \
    --change-name=2:EFI \
    "$OUTPUT"

sgdisk \
    --new=3:${ROOT_START}:${ROOT_END} \
    --typecode=3:8300 \
    --change-name=3:persistence \
    "$OUTPUT"

echo
echo "===== TARGET GPT ====="
sgdisk --print "$OUTPUT"

echo
echo "===== INSTALLING FIRMWARE PROVIDER ====="
echo "Provider: $FIRMWARE_PROVIDER"

"$INSTALL_PROVIDER" \
    "$BOARD" \
    "$OUTPUT" \
    "$BOOT" \
    "$EFI_START" \
    "$EFI_SECTORS"

DST_LOOP="$(
    losetup \
        --find \
        --show \
        --partscan \
        "$OUTPUT"
)"

udevadm settle

FIRMWARE_DST="${DST_LOOP}p1"
EFI_DST="${DST_LOOP}p2"
ROOT_DST="${DST_LOOP}p3"

[[ -b "$FIRMWARE_DST" ]] ||
    die "target firmware partition missing"

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
echo "===== INSTALLING BOARD KERNEL + METADATA ====="

cp "$KERNEL_ARTIFACTS/Image" \
    "$VERSION_DIR/vmlinuz"

cp "$KERNEL_ARTIFACTS/Image" \
    "$VERSION_DIR/vmlinuz-$KERNEL_RELEASE"

cp "$KERNEL_ARTIFACTS/kernel.config" \
    "$VERSION_DIR/config-$KERNEL_RELEASE"

cp "$KERNEL_ARTIFACTS/System.map" \
    "$VERSION_DIR/System.map-$KERNEL_RELEASE"

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

SQUASH_MODULE_DIR="$SQUASH_ROOT/usr/lib/modules/$KERNEL_RELEASE"

rm -rf "$SQUASH_MODULE_DIR"
mkdir -p "$SQUASH_MODULE_DIR"

rsync \
    -aHAX \
    --numeric-ids \
    "$MODULE_SOURCE/" \
    "$SQUASH_MODULE_DIR/"

depmod \
    -b "$SQUASH_ROOT" \
    "$KERNEL_RELEASE"

echo
echo "===== INSTALLING NETWORK FIRMWARE CLOSURE ====="

bash "$ROOT/tools/install-network-firmware.sh" \
    "$BOARD" \
    "$SQUASH_ROOT" \
    "$NETWORK_ARTIFACTS"

if [[ -x "$ROOTFS_PROVIDER" ]]; then
    echo
    echo "===== FINALIZING BOARD ROOT FILESYSTEM ====="

    "$ROOTFS_PROVIDER" \
        "$BOARD" \
        "$SQUASH_ROOT" \
        "$BOOT" \
        "$MANIFEST"
fi

echo
echo "===== INSTALLING COMMON VYOS FIRST-BOOT SUPPORT ====="

"$COMMON_ROOTFS_FINALIZER" \
    "$BOARD" \
    "$SQUASH_ROOT" \
    "$TAILSCALE_SUBNET_ROUTER" \
    "$EXTENDED_NETWORK" \
    "$BUILD_PROFILE" \
    "$KVM_OVER_IP"

echo
echo "===== ADDING GENERIC ARM CPU DISPLAY SUPPORT ====="

python3 "$ARM_CPU_OPMODE_PATCHER" "$SQUASH_ROOT"

echo
echo "===== BUILDING MATCHING VYOS INITRAMFS ====="

[[ -x "$SQUASH_ROOT/usr/sbin/update-initramfs" ]] ||
    die "VyOS root filesystem does not provide update-initramfs"

mkdir -p \
    "$SQUASH_ROOT/boot" \
    "$SQUASH_ROOT/dev" \
    "$SQUASH_ROOT/dev/pts" \
    "$SQUASH_ROOT/proc" \
    "$SQUASH_ROOT/sys" \
    "$SQUASH_ROOT/run"

cp "$KERNEL_ARTIFACTS/kernel.config" \
    "$SQUASH_ROOT/boot/config-$KERNEL_RELEASE"

cp "$KERNEL_ARTIFACTS/System.map" \
    "$SQUASH_ROOT/boot/System.map-$KERNEL_RELEASE"

mount --bind /dev "$SQUASH_ROOT/dev"
mount --bind /dev/pts "$SQUASH_ROOT/dev/pts"
mount -t proc proc "$SQUASH_ROOT/proc"
mount -t sysfs sysfs "$SQUASH_ROOT/sys"
mount -t tmpfs tmpfs "$SQUASH_ROOT/run"

chroot "$SQUASH_ROOT" /bin/bash -c "
    set -e
    export PATH=/usr/sbin:/usr/bin:/sbin:/bin
    depmod '$KERNEL_RELEASE'
    rm -f \
        '/boot/initrd.img-$KERNEL_RELEASE' \
        /boot/initrd.img
    update-initramfs -c -k '$KERNEL_RELEASE'
    test -s '/boot/initrd.img-$KERNEL_RELEASE'
"

INITRD_BUILT="$SQUASH_ROOT/boot/initrd.img-$KERNEL_RELEASE"

[[ -s "$INITRD_BUILT" ]] ||
    die "matching initramfs was not generated"

cp "$INITRD_BUILT" \
    "$VERSION_DIR/initrd.img"

cp "$INITRD_BUILT" \
    "$VERSION_DIR/initrd.img-$KERNEL_RELEASE"

echo
echo "===== INITRAMFS VALIDATION ====="

ls -lh \
    "$VERSION_DIR/initrd.img" \
    "$VERSION_DIR/initrd.img-$KERNEL_RELEASE"

lsinitramfs "$VERSION_DIR/initrd.img" \
    > "$WORK/initrd.list"

grep -q "usr/lib/modules/$KERNEL_RELEASE/" \
    "$WORK/initrd.list" ||
    die "initramfs does not contain modules for $KERNEL_RELEASE"

for required in loop ext4 overlay squashfs; do
    grep -Eq "/${required}\.ko(\.(xz|zst|gz))?$" \
        "$WORK/initrd.list" ||
        die "initramfs missing live-root module: $required"
done

unmount_chroot

# These files were only staged inside the chroot so update-initramfs could
# build against the final kernel. The persistent /boot copies above are the
# authoritative VyOS system-image files.
rm -f \
    "$SQUASH_ROOT/boot/initrd.img" \
    "$SQUASH_ROOT/boot/initrd.img-$KERNEL_RELEASE" \
    "$SQUASH_ROOT/boot/config-$KERNEL_RELEASE" \
    "$SQUASH_ROOT/boot/System.map-$KERNEL_RELEASE"

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

print(f"GRUB devicetree: /boot/{version}/dtb/{dtb}")
PY

echo
echo "===== SELECTING GRAPHICAL VYOS CONSOLE ====="

python3 "$GRUB_CONSOLE_TOOL" \
    "$DST_MNT/boot/grub" \
    --console-type tty

if [[ -x "$FINALIZE_PROVIDER" ]]; then
    echo
    echo "===== FINALIZING FIRMWARE FILESYSTEM ====="

    mount "$FIRMWARE_DST" "$FIRMWARE_MNT"

    "$FINALIZE_PROVIDER" \
        "$BOARD" \
        "$FIRMWARE_MNT" \
        "$VERSION_DIR" \
        "$KERNEL_ARTIFACTS" \
        "$GRUB_VERSION_CFG" \
        "$MANIFEST"

    sync
    umount "$FIRMWARE_MNT"
fi

echo
echo "===== RELEASE PAYLOAD VALIDATION ====="

cmp -s \
    "$KERNEL_ARTIFACTS/kernel.config" \
    "$VERSION_DIR/config-$KERNEL_RELEASE" ||
    die "installed /boot kernel config does not match the built kernel"

cmp -s \
    "$KERNEL_ARTIFACTS/System.map" \
    "$VERSION_DIR/System.map-$KERNEL_RELEASE" ||
    die "installed /boot System.map does not match the built kernel"

cmp -s \
    "$KERNEL_ARTIFACTS/Image" \
    "$VERSION_DIR/vmlinuz" ||
    die "installed kernel does not match build artifact"

cmp -s \
    "$DTB" \
    "$DTB_TARGET" ||
    die "installed DTB does not match build artifact"

GRUB_CORE="$DST_MNT/boot/grub/arm64-efi/core.efi"

if [[ -f "$GRUB_CORE" ]]; then
    strings "$GRUB_CORE" > "$WORK/grub-core.strings"
    grep -Fq '(,gpt3)/boot/grub' "$WORK/grub-core.strings" ||
        die "VyOS GRUB core does not target persistence on GPT partition 3"
fi

sync

umount "$DST_MNT/boot/efi"
umount "$DST_MNT"

losetup -d "$DST_LOOP"
DST_LOOP=""

losetup -d "$SRC_LOOP"
SRC_LOOP=""

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

[[ "$(blockdev --getsz "${CHECK_LOOP}p1")" -eq "$FIRMWARE_PART_SECTORS" ]] ||
    die "firmware partition size mismatch"

if [[ -x "$VALIDATE_PROVIDER" ]]; then
    "$VALIDATE_PROVIDER" \
        "$BOARD" \
        "${CHECK_LOOP}p1" \
        "$KERNEL_ARTIFACTS"
fi

fsck.vfat -n "${CHECK_LOOP}p2"
e2fsck -fn "${CHECK_LOOP}p3"

losetup -d "$CHECK_LOOP"

echo
echo "===== FINAL IMAGE ====="
ls -lh "$OUTPUT"
sha256sum "$OUTPUT"

echo
echo "Board image assembled successfully:"
echo "  $OUTPUT"
