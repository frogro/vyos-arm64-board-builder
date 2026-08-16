#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

KERNEL="$ROOT/cache/linux-vyos/linux-6.18.44"
BASE="$ROOT/cache/vyos-build/scripts/package-build/linux-kernel/config/arm64/vyos_defconfig"
TMP="$ROOT/work/test-kconfig-closure"

rm -rf "$TMP"
mkdir -p "$TMP"

run_test() {
    local name="$1"
    local input="$2"
    shift 2

    mkdir -p "$TMP/$name"

    printf '%s\n' "$input" > "$TMP/$name/input.config"

    "$ROOT/tools/kconfig-closure.py" \
        --kernel "$KERNEL" \
        --base-config "$BASE" \
        --requested "$TMP/$name/input.config" \
        --output "$TMP/$name/result" >/dev/null

    local result="$TMP/$name/result/resolved-fragment.config"

    for expected in "$@"; do
        if ! grep -qxF "$expected" "$result"; then
            echo "FAIL $name: missing $expected"
            echo
            cat "$result"
            exit 1
        fi
    done

    if [ -s "$TMP/$name/result/unresolved.txt" ]; then
        echo "FAIL $name: unresolved dependencies:"
        cat "$TMP/$name/result/unresolved.txt"
        exit 1
    fi

    echo "PASS $name"
}

run_test \
    fusb302 \
    'CONFIG_TYPEC_FUSB302=y' \
    'CONFIG_TYPEC_FUSB302=y' \
    'CONFIG_TYPEC_TCPM=y'

run_test \
    rp1 \
    'CONFIG_COMMON_CLK_RP1=y' \
    'CONFIG_COMMON_CLK_RP1=y' \
    'CONFIG_MISC_RP1=y' \
    'CONFIG_OF_OVERLAY=y'

run_test \
    rockchip-pcie \
    'CONFIG_PCIE_ROCKCHIP_DW=y' \
    'CONFIG_PCIE_ROCKCHIP_DW_HOST=y'

run_test \
    mtd-spinand-source-context \
    'CONFIG_MTD_SPI_NAND=y' \
    'CONFIG_MTD=y' \
    'CONFIG_MTD_SPI_NAND=y' \
    'CONFIG_SPI=y' \
    'CONFIG_SPI_MASTER=y'

echo
echo "All Kconfig closure tests passed."

