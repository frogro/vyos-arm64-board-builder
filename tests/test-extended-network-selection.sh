#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck disable=SC1091
source "$ROOT/lib/ui.sh"

[[ "$(EXTENDED_NETWORK=yes select_extended_network)" == "yes" ]]
[[ "$(EXTENDED_NETWORK=true select_extended_network)" == "yes" ]]
[[ "$(EXTENDED_NETWORK=no select_extended_network)" == "no" ]]
[[ "$(EXTENDED_NETWORK=0 select_extended_network)" == "no" ]]

# Test processes are non-interactive, so an unspecified value must safely
# select the documented default instead of blocking for input.
unset EXTENDED_NETWORK
[[ "$(select_extended_network </dev/null)" == "no" ]]

if (EXTENDED_NETWORK=invalid select_extended_network) >/dev/null 2>&1; then
    echo "ERROR: invalid Extended Network value was accepted" >&2
    exit 1
fi

grep -Fq \
    'Include common additional network drivers and firmware? [y/N]' \
    "$ROOT/lib/ui.sh"

echo "PASS: Extended Network selection contract"
