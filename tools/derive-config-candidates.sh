#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo "Usage: $0 <vyos-config> <reference-config> <output-dir>" >&2
    exit 1
fi

VYOS_CONFIG="$1"
REF_CONFIG="$2"
OUT_DIR="$3"

mkdir -p "$OUT_DIR"

normalize_config() {
    local file="$1"

    awk '
        /^CONFIG_[A-Za-z0-9_]+=/ {
            split($0, a, "=")
            print a[1] "=" substr($0, length(a[1]) + 2)
            next
        }

        /^# CONFIG_[A-Za-z0-9_]+ is not set$/ {
            name=$0
            sub(/^# /, "", name)
            sub(/ is not set$/, "", name)
            print name "=n"
        }
    ' "$file" | sort -u
}

normalize_config "$VYOS_CONFIG" > "$OUT_DIR/vyos.normalized"
normalize_config "$REF_CONFIG"  > "$OUT_DIR/reference.normalized"

awk -F= '
    NR==FNR {
        vyos[$1]=$2
        next
    }

    {
        ref[$1]=$2

        if (!($1 in vyos)) {
            print $1 "=" $2
        } else if (vyos[$1] != $2) {
            print $1 "=" $2
        }
    }
' "$OUT_DIR/vyos.normalized" "$OUT_DIR/reference.normalized" \
    | sort -u \
    > "$OUT_DIR/candidates.config"

awk -F= '
    NR==FNR {
        vyos[$1]=$2
        next
    }

    {
        if (!($1 in vyos)) {
            print $1 "=" $2
        }
    }
' "$OUT_DIR/vyos.normalized" "$OUT_DIR/reference.normalized" \
    | sort -u \
    > "$OUT_DIR/reference-only.config"

awk -F= '
    NR==FNR {
        vyos[$1]=$2
        next
    }

    {
        if (($1 in vyos) && vyos[$1] != $2) {
            print $1 ": vyos=" vyos[$1] " reference=" $2
        }
    }
' "$OUT_DIR/vyos.normalized" "$OUT_DIR/reference.normalized" \
    | sort -u \
    > "$OUT_DIR/value-differences.txt"

echo "Generated:"
echo "  $OUT_DIR/candidates.config"
echo "  $OUT_DIR/reference-only.config"
echo "  $OUT_DIR/value-differences.txt"
echo
printf 'Candidate differences: '
wc -l < "$OUT_DIR/candidates.config"
printf 'Symbols absent from VyOS config: '
wc -l < "$OUT_DIR/reference-only.config"
printf 'Different existing symbols: '
wc -l < "$OUT_DIR/value-differences.txt"
