#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 <dtb> <output-file>" >&2
    exit 1
fi

DTB="$1"
OUTPUT="$2"

command -v fdtget >/dev/null 2>&1 || {
    echo "ERROR: fdtget not found (install device-tree-compiler)" >&2
    exit 1
}

mkdir -p "$(dirname "$OUTPUT")"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

walk_node() {
    local path="$1"
    local parent_disabled="${2:-no}"
    local status=""
    local disabled="$parent_disabled"
    local compatible=""
    local child=""

    status="$(fdtget -t s "$DTB" "$path" status 2>/dev/null || true)"

    if [[ "$status" == "disabled" ]]; then
        disabled="yes"
    fi

    if [[ "$disabled" != "yes" ]]; then
        compatible="$(fdtget -t s "$DTB" "$path" compatible 2>/dev/null || true)"

        if [[ -n "$compatible" ]]; then
            # fdtget prints multiple compatible strings space-separated.
            # Most compatible strings contain no spaces themselves.
            for item in $compatible; do
                printf '%s\n' "$item" >> "$TMP"
            done
        fi
    fi

    while IFS= read -r child; do
        [[ -n "$child" ]] || continue

        if [[ "$path" == "/" ]]; then
            walk_node "/$child" "$disabled"
        else
            walk_node "$path/$child" "$disabled"
        fi
    done < <(fdtget -l "$DTB" "$path" 2>/dev/null || true)
}

walk_node "/"

sort -u "$TMP" > "$OUTPUT"

echo "Active compatible strings: $(wc -l < "$OUTPUT")"
echo "Output: $OUTPUT"
