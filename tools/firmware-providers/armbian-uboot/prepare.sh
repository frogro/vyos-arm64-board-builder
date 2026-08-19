#!/usr/bin/env bash
set -euo pipefail

BOARD="${1:?Usage: $0 <board> <hardware-branch> <boot-branch> <boot-dir>}"
HW_BRANCH="${2:?Usage: $0 <board> <hardware-branch> <boot-branch> <boot-dir>}"
BOOT_BRANCH="${3:?Usage: $0 <board> <hardware-branch> <boot-branch> <boot-dir>}"
BOOT_DIR="${4:?Usage: $0 <board> <hardware-branch> <boot-branch> <boot-dir>}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

"$ROOT/tools/build-bootchain.sh" \
    "$BOARD" \
    "$HW_BRANCH" \
    "$BOOT_BRANCH"

[[ -s "$BOOT_DIR/metadata/platform_install.sh" ]] || {
    echo "ERROR: Armbian platform_install.sh missing" >&2
    exit 1
}

[[ -d "$BOOT_DIR/artifacts" ]] || {
    echo "ERROR: Armbian U-Boot artifact directory missing" >&2
    exit 1
}

find "$BOOT_DIR/artifacts" \
    -maxdepth 1 \
    -type f \
    -printf '%f %s bytes\n' \
    | sort
