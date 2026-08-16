#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo "Usage: $0 <kernel-source> <candidate-config> <output-dir>" >&2
    exit 1
fi

KERNEL_SRC="$1"
CANDIDATES="$2"
OUT_DIR="$3"

mkdir -p "$OUT_DIR"

SYMBOLS="$OUT_DIR/kernel-symbols.txt"
VALID="$OUT_DIR/valid-candidates.config"
UNKNOWN="$OUT_DIR/unknown-symbols.config"

grep -RhsE '^[[:space:]]*(menuconfig|config)[[:space:]]+[A-Za-z0-9_]+' \
    "$KERNEL_SRC" \
    --include='Kconfig' \
    --include='Kconfig.*' |
awk '{
    if ($1 == "config" || $1 == "menuconfig")
        print "CONFIG_" $2
}' |
sort -u > "$SYMBOLS"

awk -F= '
    NR==FNR {
        valid[$1]=1
        next
    }

    {
        if ($1 in valid)
            print $0
    }
' "$SYMBOLS" "$CANDIDATES" > "$VALID"

awk -F= '
    NR==FNR {
        valid[$1]=1
        next
    }

    {
        if (!($1 in valid))
            print $0
    }
' "$SYMBOLS" "$CANDIDATES" > "$UNKNOWN"

echo "Kernel symbols:     $(wc -l < "$SYMBOLS")"
echo "Valid candidates:   $(wc -l < "$VALID")"
echo "Unknown candidates: $(wc -l < "$UNKNOWN")"
