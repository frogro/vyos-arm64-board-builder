#!/usr/bin/env bash
set -euo pipefail

BOARD="${1:?board required}"
ROOT="${2:-work/build/$BOARD}"

MANIFEST="$ROOT/boot/boot-manifest.env"
KERNEL_FILE="$ROOT/artifacts/kernel.release"
OUT="$ROOT/RELEASE_NOTES.md"

[[ -f "$MANIFEST" ]] || {
    echo "ERROR: manifest missing: $MANIFEST" >&2
    exit 1
}

[[ -s "$KERNEL_FILE" ]] || {
    echo "ERROR: kernel.release missing: $KERNEL_FILE" >&2
    exit 1
}

# shellcheck disable=SC1090
source "$MANIFEST"

KERNEL_RELEASE="$(cat "$KERNEL_FILE")"

FIRMWARE_PROVIDER="${FIRMWARE_PROVIDER:-unknown}"
FIRMWARE_VARIANT="${FIRMWARE_VARIANT:-}"
FIRMWARE_RELEASE="${FIRMWARE_RELEASE:-}"
FIRMWARE_ASSET="${FIRMWARE_ASSET:-}"
FIRMWARE_LAYOUT_MODE="${FIRMWARE_LAYOUT_MODE:-unknown}"

UBOOT_SOURCE="${UBOOT_SOURCE:-}"
UBOOT_REF="${UBOOT_REF:-}"
UBOOT_PATCHDIR="${UBOOT_PATCHDIR:-}"

FIRMWARE_PART_START="${FIRMWARE_PART_START:-unknown}"
FIRMWARE_PART_SECTORS="${FIRMWARE_PART_SECTORS:-unknown}"
EFI_START_SECTOR="${EFI_START_SECTOR:-unknown}"

cat > "$OUT" <<EOF_NOTES
# VyOS ARM64 ${BOARD_NAME} test image

Experimental VyOS ARM64 image for the ${BOARD_NAME}.

This image starts from the official VyOS ARM64 rolling userspace and keeps the native VyOS system-image/filesystem layout while adding the board-specific kernel, Device Tree, modules and firmware provider.

## Build approach

The image was created in these stages:

1. Start from the official VyOS ARM64 raw image.
2. Resolve the effective Armbian board and branch configuration.
3. Build Linux from the official VyOS kernel source and VyOS ARM64 configuration baseline.
4. Derive and apply the hardware delta required by ${BOARD_NAME}.
5. Build the matching board kernel, Device Tree and module tree.
6. Rebuild the VyOS initramfs from that final module tree.
7. Prepare the selected firmware provider and its board-specific layout.
8. Assemble the final GPT image with firmware on/raw around GPT1, EFI on GPT2 and VyOS persistence on GPT3.
9. Validate GPT, filesystems, initramfs, kernel config, DTB and payload consistency.
10. Compress the final image as \`.img.xz\`.

## Hardware and build metadata

- Board: ${BOARD_NAME}
- Board identifier: \`${BOARD}\`
- Architecture: ARM64 / aarch64
- Board family: \`${BOARD_FAMILY}\`
- Linux family: \`${LINUX_FAMILY:-unknown}\`
- SoC / boot SoC: \`${BOOT_SOC:-unknown}\`
- Device tree: \`${BOOT_FDT_FILE}\`
- Hardware reference branch: \`${HW_BRANCH}\`
- Boot reference branch: \`${BOOT_BRANCH}\`
- Kernel: \`${KERNEL_RELEASE}\`
- Armbian metadata commit: \`${ARMBIAN_COMMIT:-unknown}\`
- Firmware provider: \`${FIRMWARE_PROVIDER}\`
- Firmware variant: \`${FIRMWARE_VARIANT:-n/a}\`
- Firmware release: \`${FIRMWARE_RELEASE:-n/a}\`
- Firmware asset: \`${FIRMWARE_ASSET:-n/a}\`
- Firmware layout mode: \`${FIRMWARE_LAYOUT_MODE}\`
- U-Boot source: \`${UBOOT_SOURCE:-n/a}\`
- U-Boot ref: \`${UBOOT_REF:-n/a}\`
- U-Boot patch set: \`${UBOOT_PATCHDIR:-n/a}\`
- VyOS userspace: official VyOS rolling ARM64 build

## Image layout

The firmware provider owns the board-specific raw boot area.

- GPT1 firmware/reserved area starts at sector \`${FIRMWARE_PART_START}\`
- GPT1 length: \`${FIRMWARE_PART_SECTORS}\` sectors
- GPT2 EFI starts at sector \`${EFI_START_SECTOR}\`
- GPT3 contains VyOS persistence/system-image data

VyOS EFI/GRUB remains intact and the persistence partition stays GPT3 so the embedded GRUB prefix continues to resolve \`(,gpt3)/boot/grub\`.

## Kernel and initramfs consistency

The board kernel, DTB and module tree are generated together.

The final module tree is installed into the VyOS root filesystem, \`depmod\` is run for exactly \`${KERNEL_RELEASE}\`, and a matching VyOS initramfs is generated before the SquashFS is rebuilt.

The final \`/boot/config-${KERNEL_RELEASE}\` and \`System.map-${KERNEL_RELEASE}\` are copied from the exact kernel build artifacts.

## Validation status

Automated build validation:

- [x] Official VyOS ARM64 raw image input
- [x] Effective board configuration resolution
- [x] ${BOARD_NAME} kernel build
- [x] ${BOARD_NAME} DTB build
- [x] Kernel modules build
- [x] Matching initramfs rebuild
- [x] Final kernel config installation
- [x] Firmware-provider integration
- [x] Provider-defined three-partition GPT assembly
- [x] GRUB GPT3 prefix validation
- [x] GPT validation
- [x] Filesystem validation
- [x] Image compression
- [x] GitHub Actions artifact generation
- [ ] This exact GitHub-generated image boot tested on real ${BOARD_NAME} hardware
- [ ] This exact GitHub-generated image Ethernet tested on real ${BOARD_NAME} hardware
- [ ] VyOS system-image update tested on real ${BOARD_NAME} hardware

## Important

This is an experimental test image.

The firmware provider, kernel hardware delta and boot metadata are selected from the board configuration rather than being hard-coded into the generic image assembler. Real-hardware validation is still required for this exact generated image.
EOF_NOTES

echo "$OUT"
