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
FIRMWARE_PROVIDER="${FIRMWARE_PROVIDER:-unknown}"
FIRMWARE_VARIANT="${FIRMWARE_VARIANT:-unknown}"
EDK2_RELEASE="${EDK2_RELEASE:-unknown}"
EDK2_ASSET="${EDK2_ASSET:-unknown}"

cat > "$OUT" <<EOF_NOTES
# VyOS ARM64 ${BOARD_NAME} test image

Experimental VyOS ARM64 image for the ${BOARD_NAME}.

This image is based on an official VyOS ARM64 rolling userspace and keeps the native VyOS system-image/filesystem layout as closely as possible.

## Build approach

The image was created in several stages:

1. Start from the official VyOS ARM64 raw image.
2. Build Linux from the official VyOS kernel source/patch set and complete VyOS ARM64 config baseline.
3. Derive the ${BOARD_NAME} hardware delta from its active Device Tree and Armbian hardware metadata.
4. Build the board kernel, DTB and exact stripped module tree.
5. Rebuild the VyOS initramfs after the final module tree is installed.
6. Install the final kernel config and System.map beside the board kernel.
7. Assemble the proven RK3588 EDK2 layout with EFI on GPT2 and VyOS persistence on GPT3.
8. Validate GPT, filesystems, initramfs, kernel config, DTB and payload consistency.
9. Compress the final image as \`.img.xz\`.

## Hardware-specific components

- Board: ${BOARD_NAME}
- Architecture: ARM64 / aarch64
- Board family: ${BOARD_FAMILY}
- SoC / boot SoC: ${BOOT_SOC}
- Device tree: \`${BOOT_FDT_FILE}\`
- Hardware reference branch: \`${HW_BRANCH}\`
- Kernel: \`${KERNEL_RELEASE}\`
- Firmware provider: \`${FIRMWARE_PROVIDER}\`
- Firmware variant: \`${FIRMWARE_VARIANT}\`
- EDK2 release: \`${EDK2_RELEASE}\`
- EDK2 asset: \`${EDK2_ASSET}\`
- VyOS userspace: official VyOS rolling ARM64 build

## Image layout

For the current ROCK 5B validation path the image uses the layout already proven on real hardware:

- GPT1: 8 MiB firmware area
- GPT2: 256 MiB EFI
- GPT3: VyOS persistence/system-image partition

The EDK2 payload is copied from sector 64 onward so the generated image GPT remains authoritative. VyOS EFI/GRUB is kept intact and the embedded GRUB prefix continues to resolve \`(,gpt3)/boot/grub\`.

## Kernel and initramfs consistency

The board kernel, DTB and module tree are generated together. The final module tree is installed into the VyOS root filesystem, \`depmod\` is run for exactly \`${KERNEL_RELEASE}\`, and a new VyOS initramfs is generated from that final root filesystem before the SquashFS is rebuilt.

The final \`/boot/config-${KERNEL_RELEASE}\` and \`System.map-${KERNEL_RELEASE}\` are copied from the exact kernel build artifacts.

## Validation status

Automated build validation:

- [x] Official VyOS ARM64 raw image input
- [x] ${BOARD_NAME} kernel build
- [x] ${BOARD_NAME} DTB build
- [x] Kernel modules build
- [x] Matching initramfs rebuild
- [x] Final kernel config installation
- [x] EDK2 firmware integration
- [x] Three-partition GPT assembly
- [x] GRUB GPT3 prefix validation
- [x] GPT validation
- [x] Filesystem validation
- [x] Image compression
- [x] GitHub Actions artifact generation
- [ ] This exact GitHub-generated image boot tested on real ${BOARD_NAME} hardware
- [ ] This exact GitHub-generated image Ethernet tested on real ${BOARD_NAME} hardware
- [ ] VyOS system-image update tested on real hardware

## Important

This is an experimental test image.

The ROCK 5B EDK2 + VyOS payload architecture has already booted successfully on real ROCK 5B hardware during development. This release still needs to verify that the GitHub pipeline reproduces that working image without manual intervention.

The later firmware-provider refactor, optional extended-network driver/firmware selection, and separation of vendor/current/edge hardware references are intentionally not part of this test.
EOF_NOTES

echo "$OUT"
