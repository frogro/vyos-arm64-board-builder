#!/usr/bin/env bash
set -euo pipefail

ARMBIAN="${ARMBIAN:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/cache/armbian-build}"

BOARD="${1:?Usage: $0 <board> [requested-branch]}"
REQUESTED="${2:-auto}"

BOARD_FILE=""

for ext in conf csc wip eos tvb; do
    if [[ -f "$ARMBIAN/config/boards/${BOARD}.${ext}" ]]; then
        BOARD_FILE="$ARMBIAN/config/boards/${BOARD}.${ext}"
        break
    fi
done

[[ -n "$BOARD_FILE" ]] || {
    echo "ERROR: Armbian board definition not found: $BOARD" >&2
    exit 1
}

extract_var()
{
    local file="$1"
    local var="$2"

    grep -m1 -E \
        "(^|[[:space:]])(declare[[:space:]]+-g[[:space:]]+)?${var}=" \
        "$file" 2>/dev/null |
        sed -E \
            "s/.*${var}=[\"']?([^\"']+)[\"']?.*/\1/" ||
        true
}

TARGETS="$(extract_var "$BOARD_FILE" KERNEL_TARGET)"

[[ -n "$TARGETS" ]] || {
    echo "ERROR: KERNEL_TARGET missing for $BOARD" >&2
    exit 1
}

has_target()
{
    local wanted="$1"
    local t

    for t in ${TARGETS//,/ }; do
        [[ "$t" == "$wanted" ]] && return 0
    done

    return 1
}

if [[ "$REQUESTED" != "auto" ]]; then
    has_target "$REQUESTED" || {
        echo "ERROR: requested U-Boot branch '$REQUESTED' is not supported by $BOARD" >&2
        echo "Available targets: $TARGETS" >&2
        exit 1
    }

    printf '%s\n' "$REQUESTED"
    exit 0
fi

#
# Mainline-first U-Boot policy.
#
# Armbian board hooks frequently attach the newest board bootloader
# configuration to edge before it reaches current.
#
for candidate in edge current vendor; do
    if has_target "$candidate"; then
        printf '%s\n' "$candidate"
        exit 0
    fi
done

#
# Last-resort fallback for unusual boards.
#
for candidate in ${TARGETS//,/ }; do
    [[ -n "$candidate" ]] || continue
    printf '%s\n' "$candidate"
    exit 0
done

echo "ERROR: unable to select U-Boot branch for $BOARD" >&2
exit 1
