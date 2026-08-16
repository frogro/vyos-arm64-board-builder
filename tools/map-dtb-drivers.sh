#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
    echo "Usage: $0 <kernel-src> <compatibles-file> <candidates-config> <output-dir>" >&2
    exit 1
fi

KERNEL="$1"
COMPATIBLES="$2"
CANDIDATES="$3"
OUT="$4"

mkdir -p "$OUT"

MAP="$OUT/compatible-driver-map.tsv"
CONFIG_MAP="$OUT/compatible-config-map.tsv"
BOARD_CONFIG="$OUT/dtb-config-candidates.config"
UNRESOLVED="$OUT/unresolved-compatibles.txt"

: > "$MAP"
: > "$CONFIG_MAP"
: > "$BOARD_CONFIG"
: > "$UNRESOLVED"

find_config_for_source() {
    local src="$1"
    local dir
    local obj
    local makefile
    local line

    dir="$(dirname "$src")"
    obj="$(basename "$src" .c).o"

    while [[ "$dir" == "$KERNEL"* ]]; do
        makefile="$dir/Makefile"

        if [[ -f "$makefile" ]]; then
            while IFS= read -r line; do
                [[ -n "$line" ]] || continue

                printf '%s\n' "$line" |
                    grep -oE 'CONFIG_[A-Za-z0-9_]+' || true

            done < <(
                grep -F "$obj" "$makefile" 2>/dev/null || true
            )
        fi

        [[ "$dir" == "$KERNEL" ]] && break
        dir="$(dirname "$dir")"
    done
}

while IFS= read -r compat; do
    [[ -n "$compat" ]] || continue

    found=no

    while IFS= read -r src; do
        [[ -n "$src" ]] || continue

        found=yes

        rel="${src#"$KERNEL"/}"

        printf '%s\t%s\n' \
            "$compat" \
            "$rel" >> "$MAP"

        while IFS= read -r config; do
            [[ -n "$config" ]] || continue

            printf '%s\t%s\t%s\n' \
                "$compat" \
                "$config" \
                "$rel" >> "$CONFIG_MAP"

        done < <(find_config_for_source "$src" | sort -u)

    done < <(
        grep -RFl \
            --include='*.c' \
            --include='*.h' \
            -- "$compat" \
            "$KERNEL/drivers" \
            "$KERNEL/sound" \
            2>/dev/null || true
    )

    if [[ "$found" == no ]]; then
        printf '%s\n' "$compat" >> "$UNRESOLVED"
    fi

done < "$COMPATIBLES"

sort -u "$MAP" -o "$MAP"
sort -u "$CONFIG_MAP" -o "$CONFIG_MAP"
sort -u "$UNRESOLVED" -o "$UNRESOLVED"

cut -f2 "$CONFIG_MAP" |
    sort -u > "$OUT/dtb-config-symbols.txt"

awk -F= '
    NR==FNR {
        needed[$1]=1
        next
    }

    ($1 in needed) {
        print
    }
' "$OUT/dtb-config-symbols.txt" "$CANDIDATES" |
    sort -u > "$BOARD_CONFIG"

echo "Compatible strings:          $(wc -l < "$COMPATIBLES")"
echo "Driver mappings:             $(wc -l < "$MAP")"
echo "CONFIG mappings:             $(wc -l < "$CONFIG_MAP")"
echo "Unique DTB CONFIG symbols:   $(wc -l < "$OUT/dtb-config-symbols.txt")"
echo "Missing-from-VyOS candidates: $(wc -l < "$BOARD_CONFIG")"
echo "Unresolved compatibles:      $(wc -l < "$UNRESOLVED")"
