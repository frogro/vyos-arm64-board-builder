#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

REQUESTED_BOARD="${1:?Usage: $0 <board> [hardware-branch] [boot-branch]}"
HW_BRANCH="${2:-current}"
BOOT_BRANCH="${3:-$HW_BRANCH}"

OUT="$ROOT/work/build/$REQUESTED_BOARD/boot"
HW_CONFIG_OUT="$ROOT/work/build/$REQUESTED_BOARD/armbian-effective"
BOOT_CONFIG_OUT="$ROOT/work/build/$REQUESTED_BOARD/armbian-effective-boot-${BOOT_BRANCH}"

HW_ENV="$HW_CONFIG_OUT/config.env"
BOOT_ENV="$BOOT_CONFIG_OUT/config.env"

mkdir -p "$OUT"

#
# Resolve hardware/kernel metadata from the requested hardware branch.
#
"$ROOT/tools/resolve-armbian-effective-config.sh" \
    "$REQUESTED_BOARD" \
    "$HW_BRANCH" \
    "$HW_CONFIG_OUT" \
    >/dev/null

[[ -s "$HW_ENV" ]] || {
    echo "ERROR: effective hardware config missing: $HW_ENV" >&2
    exit 1
}

# shellcheck disable=SC1090
source "$HW_ENV"

HW_BOARD_NAME="${BOARD_NAME:-}"
HW_BOARD_VENDOR="${BOARD_VENDOR:-}"
HW_BOARD_FAMILY="${BOARDFAMILY:-}"
HW_LINUX_FAMILY="${LINUXFAMILY:-}"
HW_DTB="${BOOT_FDT_FILE:-}"
HW_PARTITION_TABLE="${IMAGE_PARTITION_TABLE:-gpt}"
HW_ARMBIAN_COMMIT="${ARMBIAN_COMMIT:-}"

#
# Resolve bootloader metadata independently from the selected boot branch.
#
"$ROOT/tools/resolve-armbian-effective-config.sh" \
    "$REQUESTED_BOARD" \
    "$BOOT_BRANCH" \
    "$BOOT_CONFIG_OUT" \
    >/dev/null

[[ -s "$BOOT_ENV" ]] || {
    echo "ERROR: effective boot config missing: $BOOT_ENV" >&2
    exit 1
}

# shellcheck disable=SC1090
source "$BOOT_ENV"

BOOT_BOARD_NAME="${BOARD_NAME:-}"
BOOT_BOARD_VENDOR="${BOARD_VENDOR:-}"
BOOT_BOARD_FAMILY="${BOARDFAMILY:-}"
BOOT_LINUX_FAMILY="${LINUXFAMILY:-}"

BOOT_CONFIG="${BOOTCONFIG:-}"
BOOT_DTB="${BOOT_FDT_FILE:-}"
BOOT_SOC_EFFECTIVE="${BOOT_SOC:-}"
BOOT_SCENARIO_EFFECTIVE="${BOOT_SCENARIO:-}"

UBOOT_SOURCE="${BOOTSOURCE:-}"
UBOOT_REF="${BOOTBRANCH:-}"
UBOOT_PATCHDIR="${BOOTPATCHDIR:-}"
UBOOT_DIR="${BOOTDIR:-}"

BOOT_ARMBIAN_COMMIT="${ARMBIAN_COMMIT:-}"

#
# Board identity must not change merely because another branch is used
# for the bootloader.
#
[[ "$HW_BOARD_NAME" == "$BOOT_BOARD_NAME" ]] || {
    echo "ERROR: board-name mismatch between hardware and boot config" >&2
    exit 1
}

[[ "$HW_BOARD_VENDOR" == "$BOOT_BOARD_VENDOR" ]] || {
    echo "ERROR: board-vendor mismatch between hardware and boot config" >&2
    exit 1
}

[[ -n "$HW_DTB" ]] || {
    echo "ERROR: effective hardware DTB missing" >&2
    exit 1
}

[[ -n "$BOOT_CONFIG" ]] || {
    echo "ERROR: effective U-Boot defconfig missing" >&2
    exit 1
}

[[ -n "$UBOOT_SOURCE" ]] || {
    echo "ERROR: effective U-Boot source missing" >&2
    exit 1
}

[[ -n "$UBOOT_REF" ]] || {
    echo "ERROR: effective U-Boot ref missing" >&2
    exit 1
}

MANIFEST="$OUT/boot-manifest.env"

{
    printf 'BOARD=%q\n' "$REQUESTED_BOARD"
    printf 'BOARD_NAME=%q\n' "$HW_BOARD_NAME"
    printf 'BOARD_VENDOR=%q\n' "$HW_BOARD_VENDOR"
    printf 'BOARD_FAMILY=%q\n' "$HW_BOARD_FAMILY"
    printf 'LINUX_FAMILY=%q\n' "$HW_LINUX_FAMILY"

    printf 'BRANCH=%q\n' "$HW_BRANCH"
    printf 'HW_BRANCH=%q\n' "$HW_BRANCH"
    printf 'BOOT_BRANCH=%q\n' "$BOOT_BRANCH"

    printf '\n'

    #
    # Kernel/hardware DTB comes from HW_BRANCH.
    #
    printf 'BOOT_FDT_FILE=%q\n' "$HW_DTB"

    #
    # Keep the bootloader-side DTB visible as separate metadata.
    #
    printf 'UBOOT_FDT_FILE=%q\n' "$BOOT_DTB"
    printf 'BOOTCONFIG=%q\n' "$BOOT_CONFIG"
    printf 'BOOT_SOC=%q\n' "$BOOT_SOC_EFFECTIVE"
    printf 'BOOT_SCENARIO=%q\n' "$BOOT_SCENARIO_EFFECTIVE"

    printf '\n'

    printf 'PARTITION_TABLE=%q\n' "$HW_PARTITION_TABLE"

    printf '\n'

    printf 'UBOOT_SOURCE=%q\n' "$UBOOT_SOURCE"
    printf 'UBOOT_REF=%q\n' "$UBOOT_REF"
    printf 'UBOOT_PATCHDIR=%q\n' "$UBOOT_PATCHDIR"
    printf 'UBOOT_DIR=%q\n' "$UBOOT_DIR"

    printf '\n'

    printf 'ARMBIAN_COMMIT=%q\n' "$HW_ARMBIAN_COMMIT"
    printf 'BOOT_ARMBIAN_COMMIT=%q\n' "$BOOT_ARMBIAN_COMMIT"
    printf 'BOOT_METADATA_SOURCE=%q\n' 'armbian-config-dump'
} > "$MANIFEST"

cat "$MANIFEST"
