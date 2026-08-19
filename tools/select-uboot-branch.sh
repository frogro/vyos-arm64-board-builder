#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BOARD="${1:?Usage: $0 <board> [requested-boot-branch] [hardware-branch]}"
REQUESTED="${2:-auto}"
HW_BRANCH="${3:-current}"
EFFECTIVE_BOARD="${ARMBIAN_BOARD:-$BOARD}"

OUT="$ROOT/work/build/$BOARD/armbian-branch-selection"
ENVFILE="$OUT/config.env"

#
# Use Armbian's evaluated board configuration as the only source of
# truth. Do not statically parse config/boards/*.conf here.
#
    "$ROOT/tools/resolve-armbian-effective-config.sh" \
    "$EFFECTIVE_BOARD" \
    "$HW_BRANCH" \
    "$OUT" \
    >/dev/null

[[ -s "$ENVFILE" ]] || {
    echo "ERROR: effective Armbian config missing: $ENVFILE" >&2
    exit 1
}

# shellcheck disable=SC1090
source "$ENVFILE"

TARGETS="${KERNEL_TARGET:-}"

[[ -n "$TARGETS" ]] || {
    echo "ERROR: effective KERNEL_TARGET missing for $BOARD" >&2
    exit 1
}

has_target()
{
    local wanted="$1"
    local target

    for target in ${TARGETS//,/ }; do
        [[ "$target" == "$wanted" ]] && return 0
    done

    return 1
}

#
# Explicit request always wins, but must be valid.
#
if [[ "$REQUESTED" != "auto" ]]; then
    has_target "$REQUESTED" || {
        echo "ERROR: requested boot branch '$REQUESTED' is not supported by $BOARD" >&2
        echo "Available targets: $TARGETS" >&2
        exit 1
    }

    printf '%s\n' "$REQUESTED"
    exit 0
fi

#
# AUTO policy:
#
# Keep the hardware reference branch when that branch is supported.
# This prevents an implicit current-kernel / edge-U-Boot mix.
#
if has_target "$HW_BRANCH"; then
    printf '%s\n' "$HW_BRANCH"
    exit 0
fi

#
# Conservative generic fallbacks for unusual boards.
#
for candidate in current vendor edge; do
    if has_target "$candidate"; then
        printf '%s\n' "$candidate"
        exit 0
    fi
done

#
# Final fallback: first advertised target.
#
for candidate in ${TARGETS//,/ }; do
    [[ -n "$candidate" ]] || continue
    printf '%s\n' "$candidate"
    exit 0
done

echo "ERROR: unable to select boot branch for $BOARD" >&2
exit 1
