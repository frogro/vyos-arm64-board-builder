#!/usr/bin/env bash
set -euo pipefail

BOARD="${1:?board required}"
ROOT="${2:-work/build/$BOARD}"

MANIFEST="$ROOT/boot/boot-manifest.env"
KERNEL_FILE="$ROOT/artifacts/kernel.release"
NETWORK_SELECTION="$ROOT/selection/extended-network.env"
FEATURE_SELECTION="$ROOT/selection/feature-profiles.env"
RELEASE_ENV="$ROOT/release.env"
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

EXTENDED_NETWORK="no"
TAILSCALE_SUBNET_ROUTER="no"
BUILD_PROFILE="base"
KVM_OVER_IP="no"

if [[ -f "$NETWORK_SELECTION" ]]; then
    # shellcheck disable=SC1090
    source "$NETWORK_SELECTION"
fi

if [[ -f "$FEATURE_SELECTION" ]]; then
    # shellcheck disable=SC1090
    source "$FEATURE_SELECTION"
fi

if [[ -f "$RELEASE_ENV" ]]; then
    # shellcheck disable=SC1090
    source "$RELEASE_ENV"
fi

KERNEL_RELEASE="$(cat "$KERNEL_FILE")"

FIRMWARE_PROVIDER="${FIRMWARE_PROVIDER:-unknown}"
FIRMWARE_VARIANT="${FIRMWARE_VARIANT:-}"
FIRMWARE_RELEASE="${FIRMWARE_RELEASE:-}"
FIRMWARE_ASSET="${FIRMWARE_ASSET:-}"
FIRMWARE_LAYOUT_MODE="${FIRMWARE_LAYOUT_MODE:-unknown}"
VYOS_VERSION="${VYOS_VERSION:-unknown}"
RELEASE_BASENAME="${RELEASE_BASENAME:-vyos-${BOARD}}"
UPDATE_PROVIDER="${UPDATE_PROVIDER:-unknown}"

UBOOT_SOURCE="${UBOOT_SOURCE:-}"
UBOOT_REF="${UBOOT_REF:-}"
UBOOT_PATCHDIR="${UBOOT_PATCHDIR:-}"

FIRMWARE_PART_START="${FIRMWARE_PART_START:-unknown}"
FIRMWARE_PART_SECTORS="${FIRMWARE_PART_SECTORS:-unknown}"
EFI_START_SECTOR="${EFI_START_SECTOR:-unknown}"

if [[ "$FIRMWARE_PROVIDER" == "raspberrypi-native" ]]; then
    BOOT_APPROACH="Raspberry Pi EEPROM/Boot ROM, native Raspberry Pi firmware on GPT1, config.txt, the board kernel and its matching initramfs. The original VyOS EFI/GRUB filesystem remains present on GPT2 but is not the default Pi boot path."
    LAYOUT_DESCRIPTION="- GPT1 is a 512 MiB FAT32 \`RPICFG\` partition containing pinned Raspberry Pi firmware plus the matching kernel, initramfs and BCM2712 Device Tree
- GPT2 is the unchanged official VyOS EFI filesystem
- GPT3 is the unchanged VyOS persistence/system-image filesystem"
    UPDATE_STATUS="The release includes a VyOS system-image ISO, but native Raspberry Pi firmware boots the kernel from FAT rather than through GRUB. An \`add system image\` operation therefore also requires synchronization of the selected board kernel, initramfs and DTB to \`RPICFG\`. Do not use the ISO on this provider until that synchronization gate is implemented and hardware-tested."
    PROVIDER_VALIDATION="- [x] Raspberry Pi firmware-partition filesystem validation
- [x] \`config.txt\`, \`cmdline.txt\`, kernel, initramfs and BCM2712 DTB validation
- [x] FAT kernel equality with the built kernel artifact"
else
    BOOT_APPROACH="The provider-specific firmware hands off to the unchanged official VyOS EFI/GRUB path."
    LAYOUT_DESCRIPTION="- GPT1 firmware/reserved area starts at sector \`${FIRMWARE_PART_START}\`
- GPT1 length: \`${FIRMWARE_PART_SECTORS}\` sectors
- GPT2 contains the original VyOS EFI filesystem
- GPT3 contains VyOS persistence/system-image data"
    if [[ "$UPDATE_PROVIDER" == "efi-firmware-dtb" ]]; then
        UPDATE_STATUS="VyOS EFI/GRUB remains intact and persistence stays GPT3. The release includes an ISO for the standard \`add system image\` workflow. This provider supplies the live Device Tree through firmware; the path has been validated on ROCK 5B hardware and still requires validation for every other exact board/provider combination."
    else
        UPDATE_STATUS="The release includes a VyOS system-image ISO. This provider requires a per-version DTB/GRUB synchronization gate after \`add system image\`; do not treat the ISO as production-ready until that gate and this exact board have been hardware-tested."
    fi
    PROVIDER_VALIDATION="- [x] Provider-defined firmware integration"
fi

cat > "$OUT" <<EOF_NOTES
# VyOS ${VYOS_VERSION} for ${BOARD_NAME}

Experimental VyOS ARM64 initial-installation image and system-update payload for the ${BOARD_NAME}.

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
10. Build and checksum a standard VyOS system-image update ISO.
11. Compress and checksum the initial-installation image as \`.img.xz\`.

## Hardware and build metadata

- Board: ${BOARD_NAME}
- Board identifier: \`${BOARD}\`
- Architecture: ARM64 / aarch64
- Board family: \`${BOARD_FAMILY}\`
- Linux family: \`${LINUX_FAMILY:-unknown}\`
- SoC / boot SoC: \`${BOOT_SOC:-unknown}\`
- Device tree: \`${BOOT_FDT_FILE}\`
- Hardware reference branch: \`${HW_BRANCH}\`
- Hardware reference selection: \`${HW_SELECTION_MODE:-unknown}\`
- VyOS/reference kernel line: \`${VYOS_KERNEL_MAJOR_MINOR:-unknown}\` / \`${REFERENCE_KERNEL_MAJOR_MINOR:-unknown}\`
- Boot reference branch: \`${BOOT_BRANCH}\`
- Kernel: \`${KERNEL_RELEASE}\`
- Build profile: \`${BUILD_PROFILE}\`
- Extended Network drivers and firmware: \`${EXTENDED_NETWORK}\`
- Tailscale subnet-router preparation: \`${TAILSCALE_SUBNET_ROUTER}\`
- KVM-over-IP preparation: \`${KVM_OVER_IP}\`
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
- VyOS version: \`${VYOS_VERSION}\`
- Initial installation: \`${RELEASE_BASENAME}.img.xz\`
- System-image update: \`${RELEASE_BASENAME}.iso\`
- System-image update provider: \`${UPDATE_PROVIDER}\`

## Image layout

${BOOT_APPROACH}

${LAYOUT_DESCRIPTION}

${UPDATE_STATUS}

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
- [x] Network firmware closure/report generation
${PROVIDER_VALIDATION}
- [x] Provider-defined three-partition GPT assembly
- [x] GRUB GPT3 prefix validation
- [x] GPT validation
- [x] Filesystem validation
- [x] Image compression
- [x] System-image ISO generation and checksum validation
- [x] First-boot persistence expansion support
- [x] Generic ARM CPU information display compatibility
- [x] GitHub Actions artifact generation
- [ ] This exact GitHub-generated image boot tested on real ${BOARD_NAME} hardware
- [ ] This exact GitHub-generated image Ethernet tested on real ${BOARD_NAME} hardware
- [ ] VyOS system-image update tested on real ${BOARD_NAME} hardware

## Important

This is an experimental test image.

The firmware provider, kernel hardware delta and boot metadata are selected from the board configuration rather than being hard-coded into the generic image assembler. Real-hardware validation is still required for this exact generated image.

When Extended Network is enabled, the image contains the curated optional runtime modules which the selected Linux Kconfig can satisfy as modules. Exact enabled/skipped symbols and installed/missing firmware files are published beside the image in \`extended-network-report.txt\` and the network firmware manifest. Board-required drivers remain independent of this option.

When KVM-over-IP preparation is enabled, the image contains generic USB UVC
capture and USB HID gadget kernel capabilities, a Bookworm-built µStreamer
binary and a read-only runtime audit. No streamer is started, no firewall port
is opened, and HID operation remains conditional on a device/OTG-capable USB
controller.
EOF_NOTES

echo "$OUT"
