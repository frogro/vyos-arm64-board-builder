#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BOARD="${1:?Usage: $0 <board> [hardware-branch] [boot-branch] [provider]}"
HW_BRANCH="${2:-current}"
BOOT_BRANCH_REQUESTED="${3:-auto}"
PROVIDER_REQUESTED="${4:-auto}"

BOOT="$ROOT/work/build/$BOARD/boot"
mkdir -p "$BOOT"

PROVIDER_ENV="$(
    "$ROOT/tools/resolve-firmware-provider.sh" \
        "$BOARD" \
        "$PROVIDER_REQUESTED"
)"

eval "$PROVIDER_ENV"

BOOT_BRANCH="$(
    "$ROOT/tools/select-uboot-branch.sh" \
        "$BOARD" \
        "$BOOT_BRANCH_REQUESTED" \
        "$HW_BRANCH"
)"

echo "===== FIRMWARE PROVIDER ====="
echo "Board:             $BOARD"
echo "Hardware branch:   $HW_BRANCH"
echo "Boot branch:       $BOOT_BRANCH"
echo "Provider:          $FIRMWARE_PROVIDER"
echo "Variant:           ${FIRMWARE_VARIANT:-}"
echo

#
# Always establish the common boot manifest first.
#
"$ROOT/tools/resolve-bootchain.sh" \
    "$BOARD" \
    "$HW_BRANCH" \
    "$BOOT_BRANCH" \
    >/dev/null

PROVIDER_DIR="$ROOT/tools/firmware-providers/$FIRMWARE_PROVIDER"
PREPARE="$PROVIDER_DIR/prepare.sh"
LAYOUT="$PROVIDER_DIR/layout.env"

[[ -x "$PREPARE" ]] || {
    echo "ERROR: provider prepare implementation missing: $PREPARE" >&2
    exit 1
}

[[ -f "$LAYOUT" ]] || {
    echo "ERROR: provider layout contract missing: $LAYOUT" >&2
    exit 1
}

export \
    FIRMWARE_PROVIDER \
    FIRMWARE_VARIANT \
    FIRMWARE_RELEASE \
    FIRMWARE_ASSET \
    FIRMWARE_URL

#
# Every provider receives the same interface.
#
"$PREPARE" \
    "$BOARD" \
    "$HW_BRANCH" \
    "$BOOT_BRANCH" \
    "$BOOT"

MANIFEST="$BOOT/boot-manifest.env"

[[ -s "$MANIFEST" ]] || {
    echo "ERROR: boot manifest missing after firmware preparation" >&2
    exit 1
}

#
# Provider owns its layout contract. The common boot manifest is
# sourced first so a provider may derive layout from evaluated
# Armbian metadata such as OFFSET.
#
# shellcheck disable=SC1090
source "$MANIFEST"

# shellcheck disable=SC1090
source "$LAYOUT"

: "${FIRMWARE_LAYOUT_MODE:?provider did not define FIRMWARE_LAYOUT_MODE}"
: "${FIRMWARE_PART_START:?provider did not define FIRMWARE_PART_START}"
: "${FIRMWARE_PART_SECTORS:?provider did not define FIRMWARE_PART_SECTORS}"
: "${EFI_START_SECTOR:?provider did not define EFI_START_SECTOR}"

{
    printf '\n'

    printf 'FIRMWARE_PROVIDER=%q\n' \
        "$FIRMWARE_PROVIDER"

    printf 'FIRMWARE_VARIANT=%q\n' \
        "${FIRMWARE_VARIANT:-}"

    printf 'FIRMWARE_RELEASE=%q\n' \
        "${FIRMWARE_RELEASE:-}"

    printf 'FIRMWARE_ASSET=%q\n' \
        "${FIRMWARE_ASSET:-}"

    printf 'FIRMWARE_URL=%q\n' \
        "${FIRMWARE_URL:-}"

    printf 'FIRMWARE_LAYOUT_MODE=%q\n' \
        "$FIRMWARE_LAYOUT_MODE"

    for name in \
        FIRMWARE_PART_START \
        FIRMWARE_PART_SECTORS \
        FIRMWARE_SKIP_SECTORS \
        EFI_START_SECTOR
    do
        if [[ -n "${!name:-}" ]]; then
            printf '%s=%q\n' \
                "$name" \
                "${!name}"
        fi
    done
} >> "$MANIFEST"

echo
echo "===== FINAL BOOT/FIRMWARE MANIFEST ====="
cat "$MANIFEST"
