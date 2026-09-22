#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BOARD="${1:?Usage: $0 <board> [requested-provider]}"
REQUESTED="${2:-auto}"

PROFILE="${FIRMWARE_PROVIDER_PROFILE:-$ROOT/profiles/firmware-providers.conf}"

[[ -f "$PROFILE" ]] || {
    echo "ERROR: firmware provider profile missing: $PROFILE" >&2
    exit 1
}

find_entry()
{
    local wanted="$1"

    awk -F'|' \
        -v board="$wanted" \
        '
        /^[[:space:]]*#/ { next }
        /^[[:space:]]*$/ { next }

        $1 == board {
            print
            exit
        }
        ' \
        "$PROFILE"
}

ENTRY="$(find_entry "$BOARD")"

if [[ -z "$ENTRY" ]]; then
    ENTRY="$(find_entry '*')"
fi

[[ -n "$ENTRY" ]] || {
    echo "ERROR: no firmware-provider rule for board: $BOARD" >&2
    exit 1
}

IFS='|' read -r \
    PROFILE_BOARD \
    PROFILE_PROVIDER \
    PROFILE_VARIANT \
    PROFILE_RELEASE \
    PROFILE_ASSET \
    PROFILE_URL \
    <<< "$ENTRY"

if [[ "$REQUESTED" == "auto" ]]; then
    PROVIDER="$PROFILE_PROVIDER"
else
    PROVIDER="$REQUESTED"
fi

[[ -n "$PROVIDER" ]] || {
    echo "ERROR: empty firmware provider for board: $BOARD" >&2
    exit 1
}

PROVIDER_DIR="$ROOT/tools/firmware-providers/$PROVIDER"

[[ -d "$PROVIDER_DIR" ]] || {
    echo "ERROR: firmware provider implementation missing: $PROVIDER_DIR" >&2
    exit 1
}

#
# Only use provider-specific metadata from the profile when the
# selected provider is the provider named by that exact/default rule.
#
VARIANT=""
RELEASE=""
ASSET=""
URL=""

if [[ "$PROVIDER" == "$PROFILE_PROVIDER" ]]; then
    VARIANT="$PROFILE_VARIANT"
    RELEASE="$PROFILE_RELEASE"
    ASSET="$PROFILE_ASSET"
    URL="$PROFILE_URL"
fi

printf 'FIRMWARE_PROVIDER=%q\n' "$PROVIDER"
printf 'FIRMWARE_VARIANT=%q\n' "$VARIANT"
printf 'FIRMWARE_RELEASE=%q\n' "$RELEASE"
printf 'FIRMWARE_ASSET=%q\n' "$ASSET"
printf 'FIRMWARE_URL=%q\n' "$URL"
