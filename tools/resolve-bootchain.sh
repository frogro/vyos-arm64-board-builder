#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARMBIAN="${ARMBIAN:-$ROOT/cache/armbian-build}"

BOARD="${1:?Usage: $0 <board> [branch]}"
BRANCH="${2:-current}"

BOARD_CONF="$ARMBIAN/config/boards/${BOARD}.conf"

[[ -f "$BOARD_CONF" ]] || {
    echo "ERROR: board definition not found: $BOARD_CONF" >&2
    exit 1
}

get_var() {
    local file="$1"
    local name="$2"

    sed -n \
        "s/^[[:space:]]*\\(declare[[:space:]]\\+-g[[:space:]]\\+\\)\\?${name}=[\"']\\?\\([^\"'#]*\\).*/\\2/p" \
        "$file" |
        head -n1 |
        sed 's/[[:space:]]*$//'
}

BOARD_NAME="$(get_var "$BOARD_CONF" BOARD_NAME)"
BOARD_VENDOR="$(get_var "$BOARD_CONF" BOARD_VENDOR)"
BOARDFAMILY="$(get_var "$BOARD_CONF" BOARDFAMILY)"
BOOTCONFIG="$(get_var "$BOARD_CONF" BOOTCONFIG)"
BOOT_FDT_FILE="$(get_var "$BOARD_CONF" BOOT_FDT_FILE)"
BOOT_SCENARIO="$(get_var "$BOARD_CONF" BOOT_SCENARIO)"
IMAGE_PARTITION_TABLE="$(get_var "$BOARD_CONF" IMAGE_PARTITION_TABLE)"

FAMILY_FILE="$ARMBIAN/config/sources/families/${BOARDFAMILY}.conf"

if [[ ! -f "$FAMILY_FILE" ]]; then
    echo "ERROR: family file not found: $FAMILY_FILE" >&2
    exit 1
fi

COMMON_INCLUDE="$ARMBIAN/config/sources/families/include/rockchip64_common.inc"

BOOT_SOC="$(
    expr "${BOOTCONFIG}" : '.*\(rk[[:digit:]]\+.*\)_.*' || true
)"

BOOT_SCENARIO_EFFECTIVE="$BOOT_SCENARIO"
DDR_BLOB=""
BL31_BLOB=""
UBOOT_SOURCE=""
UBOOT_REF=""

case "$BOARDFAMILY" in
    rockchip-rk3588|rockchip64)
        [[ -f "$COMMON_INCLUDE" ]] || {
            echo "ERROR: Rockchip common include missing" >&2
            exit 1
        }

        if [[ -z "$BOOT_SCENARIO_EFFECTIVE" ]]; then
            BOOT_SCENARIO_EFFECTIVE="spl-blobs"
        fi

        if [[ "$BOOT_SOC" == "rk3588" ]]; then
            DDR_BLOB="$(
                sed -n \
                    's/.*DDR_BLOB="${DDR_BLOB:-"\([^"]*\)".*/\1/p' \
                    "$COMMON_INCLUDE" |
                    grep 'rk3588_' |
                    head -1
            )"

            BL31_BLOB="$(
                sed -n \
                    's/.*BL31_BLOB="${BL31_BLOB:-"\([^"]*\)".*/\1/p' \
                    "$COMMON_INCLUDE" |
                    grep 'rk3588_' |
                    head -1
            )"
        fi

        #
        # Resolve U-Boot defaults from the selected board family only.
        #
        UBOOT_SOURCE="$(
            sed -n                 -e 's/^[[:space:]]*BOOTSOURCE=["'\'']\([^"'\'']*\)["'\''].*/\1/p'                 -e 's/^[[:space:]]*declare[[:space:]]\+-g[[:space:]]\+BOOTSOURCE=["'\'']\([^"'\'']*\)["'\''].*/\1/p'                 "$FAMILY_FILE" |
                head -1
        )"

        UBOOT_REF="$(
            sed -n                 -e 's/^[[:space:]]*BOOTBRANCH=["'\'']\([^"'\'']*\)["'\''].*/\1/p'                 -e 's/^[[:space:]]*declare[[:space:]]\+-g[[:space:]]\+BOOTBRANCH=["'\'']\([^"'\'']*\)["'\''].*/\1/p'                 "$FAMILY_FILE" |
                head -1
        )"

        UBOOT_PATCHDIR="$(
            sed -n                 -e 's/^[[:space:]]*BOOTPATCHDIR=["'\'']\([^"'\'']*\)["'\''].*/\1/p'                 -e 's/^[[:space:]]*declare[[:space:]]\+-g[[:space:]]\+BOOTPATCHDIR=["'\'']\([^"'\'']*\)["'\''].*/\1/p'                 "$FAMILY_FILE" |
                head -1
        )"

        ;;

    *)
        echo "ERROR: unsupported family resolver: $BOARDFAMILY" >&2
        exit 1
        ;;
esac

case "$BOOT_SCENARIO_EFFECTIVE" in
    spl-blobs)
        BOOT_LAYOUT="rockchip-idb-itb"
        ARTIFACT_1="idbloader.img"
        OFFSET_1=32768
        ARTIFACT_2="u-boot.itb"
        OFFSET_2=8388608
        ;;
    *)
        echo "ERROR: unsupported boot scenario: $BOOT_SCENARIO_EFFECTIVE" >&2
        exit 1
        ;;
esac

OUT="$ROOT/work/build/$BOARD/boot"
mkdir -p "$OUT"

{
    printf 'BOARD=%q\n' "$BOARD"
    printf 'BOARD_NAME=%q\n' "$BOARD_NAME"
    printf 'BOARD_VENDOR=%q\n' "$BOARD_VENDOR"
    printf 'BOARD_FAMILY=%q\n' "$BOARDFAMILY"
    printf 'BRANCH=%q\n' "$BRANCH"
    printf '\n'

    printf 'BOOTCONFIG=%q\n' "$BOOTCONFIG"
    printf 'BOOT_FDT_FILE=%q\n' "$BOOT_FDT_FILE"
    printf 'BOOT_SOC=%q\n' "$BOOT_SOC"
    printf 'BOOT_SCENARIO=%q\n' "$BOOT_SCENARIO_EFFECTIVE"
    printf 'BOOT_LAYOUT=%q\n' "$BOOT_LAYOUT"
    printf '\n'

    printf 'PARTITION_TABLE=%q\n' "${IMAGE_PARTITION_TABLE:-gpt}"
    printf '\n'

    printf 'UBOOT_SOURCE=%q\n' "$UBOOT_SOURCE"
    printf 'UBOOT_REF=%q\n' "$UBOOT_REF"
    printf 'UBOOT_PATCHDIR=%q\n' "$UBOOT_PATCHDIR"
    printf '\n'

    printf 'DDR_BLOB=%q\n' "$DDR_BLOB"
    printf 'BL31_BLOB=%q\n' "$BL31_BLOB"
    printf '\n'

    printf 'ARTIFACT_1=%q\n' "$ARTIFACT_1"
    printf 'OFFSET_1=%q\n' "$OFFSET_1"
    printf 'ARTIFACT_2=%q\n' "$ARTIFACT_2"
    printf 'OFFSET_2=%q\n' "$OFFSET_2"
} > "$OUT/boot-manifest.env"

cat "$OUT/boot-manifest.env"
