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

# shellcheck disable=SC1090
source "$MANIFEST"

KERNEL_RELEASE="$(cat "$KERNEL_FILE")"

cat > "$OUT" <<EOF_NOTES
# VyOS ARM64 ${BOARD_NAME} test image

Experimental VyOS ARM64 image for the ${BOARD_NAME}.

This image is based on an official VyOS ARM64 rolling userspace and keeps the native VyOS system-image/filesystem layout as closely as possible.

## Build approach

The image was created in several stages:

1. Build a generic official VyOS ARM64 raw image.
2. Build the Linux kernel from the official VyOS/kernel.org source with the official VyOS kernel patches.
3. Derive the ${BOARD_NAME} hardware configuration from the Armbian board/family metadata.
4. Apply only the board-specific kernel configuration required for the ${BOARD_NAME}.
5. Build the board-specific device tree and kernel modules.
6. Build the Rockchip/U-Boot boot chain using the board-specific Armbian boot metadata.
7. Assemble the board-specific boot chain together with the VyOS ARM64 filesystem/system-image layout.
8. Validate the final GPT layout and filesystems.
9. Compress the final image as \`.img.xz\`.

## Hardware-specific components

- Board: ${BOARD_NAME}
- Architecture: ARM64 / aarch64
- Board family: ${BOARD_FAMILY}
- SoC / boot SoC: ${BOOT_SOC}
- Device tree: \`${BOOT_FDT_FILE}\`
- Boot configuration: \`${BOOTCONFIG}\`
- Boot layout: \`${BOOT_LAYOUT}\`
- Kernel: \`${KERNEL_RELEASE}\`
- U-Boot source: \`${UBOOT_SOURCE}\`
- U-Boot reference: \`${UBOOT_REF}\`
- VyOS userspace: official VyOS rolling ARM64 build

## VyOS layout

Unlike the earlier experimental Armbian-rootfs based approach, this image starts with an official VyOS ARM64 raw image and preserves the native VyOS filesystem and system-image structure.

The board-specific kernel, DTB, kernel modules and boot chain are integrated separately.

The goal is to remain compatible with the normal VyOS system-image workflow, including future use of:

\`add system image\`

where possible.

## Image layout

The final image uses a board-specific GPT layout with a reserved area at the beginning of the disk for the board boot chain, followed by:

- EFI partition
- VyOS persistence/system-image partition

The bootloader is installed using the board-specific Armbian-derived bootloader installation logic rather than assuming one generic Rockchip boot layout.

## Validation status

Automated build validation:

- [x] VyOS ARM64 raw image build
- [x] ${BOARD_NAME} kernel build
- [x] ${BOARD_NAME} DTB build
- [x] Kernel modules build
- [x] U-Boot/boot-chain build
- [x] Board image assembly
- [x] GPT validation
- [x] Filesystem validation
- [x] Image compression
- [x] GitHub Actions artifact generation
- [ ] Boot tested on real ${BOARD_NAME} hardware
- [ ] Ethernet tested on real ${BOARD_NAME} hardware
- [ ] Console tested on real ${BOARD_NAME} hardware
- [ ] VyOS system-image update tested on real hardware

## Important

This is an early experimental test image.

The complete automated build pipeline finished successfully, but this image has not yet been confirmed to boot on real ${BOARD_NAME} hardware.

Please test on removable media first.

Feedback about boot behaviour, serial console, Ethernet, storage, USB, VyOS \`add system image\`, reboot and rollback behaviour is very welcome.
EOF_NOTES

echo "$OUT"
