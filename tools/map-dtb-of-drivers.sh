#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
    echo "Usage: $0 <kernel-src> <compatibles-file> <candidate-config> <output-dir>" >&2
    exit 1
fi

KERNEL="$1"
COMPATIBLES="$2"
CANDIDATES="$3"
OUT="$4"

mkdir -p "$OUT"

SOURCE_MAP="$OUT/compatible-source-map.tsv"
CONFIG_MAP="$OUT/compatible-config-map.tsv"
SYMBOLS="$OUT/dtb-config-symbols.txt"
BOARD_CONFIG="$OUT/dtb-config-candidates.config"
UNRESOLVED="$OUT/unresolved-compatibles.txt"

: > "$SOURCE_MAP"
: > "$CONFIG_MAP"
: > "$SYMBOLS"
: > "$BOARD_CONFIG"
: > "$UNRESOLVED"

#
# Find CONFIG symbols controlling a source file.
#
# Handles common cases such as:
#
#   obj-$(CONFIG_FOO) += foo.o
#
# and also walks parent Makefiles when a directory is selected as:
#
#   obj-$(CONFIG_FOO) += rockchip/
#
#
find_configs_for_source() {
    local src="$1"
    local dir
    local obj
    local makefile
    local escaped_obj
    local parent_obj
    local escaped_parent

    dir="$(dirname "$src")"
    obj="$(basename "$src" .c).o"
    makefile="$dir/Makefile"

    [[ -f "$makefile" ]] || return 0

    #
    # 1. Direct object mapping:
    #
    # obj-$(CONFIG_FOO) += foo.o
    #
    escaped_obj="$(
        printf '%s\n' "$obj" |
        sed 's/[][\/.^$*+?(){}|]/\\&/g'
    )"

    grep -E \
        "(^|[[:space:]])${escaped_obj}([[:space:]]|$)" \
        "$makefile" 2>/dev/null |
        grep -oE 'CONFIG_[A-Za-z0-9_]+' ||
        true

    #
    # 2. One level of composite Kbuild objects:
    #
    # macb-y := macb_main.o
    # obj-$(CONFIG_MACB) += macb.o
    #
    # Also covers common forms such as:
    #
    # foo-objs += foo_core.o
    # foo-y    += foo_core.o
    #
    while IFS= read -r parent_obj; do
        [[ -n "$parent_obj" ]] || continue

        escaped_parent="$(
            printf '%s\n' "${parent_obj}.o" |
            sed 's/[][\/.^$*+?(){}|]/\\&/g'
        )"

        grep -E \
            "(^|[[:space:]])${escaped_parent}([[:space:]]|$)" \
            "$makefile" 2>/dev/null |
            grep -oE 'CONFIG_[A-Za-z0-9_]+' ||
            true

    done < <(
        awk -v obj="$obj" '
            /^[A-Za-z0-9_.-]+-(y|objs)[[:space:]]*[:+]?=/ {
                lhs=$1
                sub(/-(y|objs)$/, "", lhs)

                for (i=1; i<=NF; i++) {
                    if ($i == obj) {
                        print lhs
                        break
                    }
                }
            }
        ' "$makefile"
    )
}

#
# Escape regex metacharacters in a DT compatible string.
#
regex_escape() {
    printf '%s' "$1" |
        sed 's/[][\/.^$*+?(){}|]/\\&/g'
}

while IFS= read -r compat; do
    [[ -n "$compat" ]] || continue

    #
    # Structural DT compatibles describe bus topology rather than a
    # unique hardware driver.  "simple-bus" in particular occurs in
    # multiple unrelated platform drivers (generic OF, i.MX, TI), so
    # mapping it to every matching CONFIG would create false positives.
    #
    case "$compat" in
        simple-bus)
            continue
            ;;
    esac

    escaped="$(regex_escape "$compat")"
    found="no"

    #
    # Search ONLY real OF compatible assignments:
    #
    # .compatible = "vendor,device"
    #
    # This deliberately ignores arbitrary occurrences in comments,
    # documentation and unrelated source code.
    #
    while IFS= read -r match; do
        [[ -n "$match" ]] || continue

        src="${match%%:*}"

        [[ "$src" == *.c ]] || continue

        found="yes"
        rel="${src#"$KERNEL"/}"

        printf '%s\t%s\n' \
            "$compat" \
            "$rel" >> "$SOURCE_MAP"

        while IFS= read -r config; do
            [[ -n "$config" ]] || continue

            printf '%s\t%s\t%s\n' \
                "$compat" \
                "$config" \
                "$rel" >> "$CONFIG_MAP"

        done < <(
            find_configs_for_source "$src" |
                sort -u
        )

    done < <(
        grep -RnsE \
            --include='*.c' \
            "\.compatible[[:space:]]*=[[:space:]]*\"${escaped}\"" \
            "$KERNEL/drivers" \
            "$KERNEL/sound" \
            2>/dev/null || true
    )

    if [[ "$found" == "no" ]]; then
        printf '%s\n' "$compat" >> "$UNRESOLVED"
    fi

done < "$COMPATIBLES"

sort -u "$SOURCE_MAP" -o "$SOURCE_MAP"
sort -u "$CONFIG_MAP" -o "$CONFIG_MAP"
sort -u "$UNRESOLVED" -o "$UNRESOLVED"

cut -f2 "$CONFIG_MAP" |
    sort -u > "$SYMBOLS"

#
# Keep only CONFIG values that differ from VyOS.
#
awk -F= '
    NR==FNR {
        needed[$1]=1
        next
    }

    ($1 in needed) {
        print
    }
' "$SYMBOLS" "$CANDIDATES" |
    sort -u > "$BOARD_CONFIG"

echo
echo "Strict OF mapping complete"
echo
echo "Compatible strings:           $(wc -l < "$COMPATIBLES")"
echo "Matched source mappings:      $(wc -l < "$SOURCE_MAP")"
echo "CONFIG mappings:              $(wc -l < "$CONFIG_MAP")"
echo "Unique driver CONFIG symbols: $(wc -l < "$SYMBOLS")"
echo "Missing-from-VyOS candidates: $(wc -l < "$BOARD_CONFIG")"
echo "Unresolved compatibles:       $(wc -l < "$UNRESOLVED")"
