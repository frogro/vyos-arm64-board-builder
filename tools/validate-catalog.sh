#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

INPUT="${1:?Usage: $0 <catalog-directory-or-zip> <VyOS-kernel-version> [report.json]}"
VYOS_KERNEL="${2:?Usage: $0 <catalog-directory-or-zip> <VyOS-kernel-version> [report.json]}"
REPORT="${3:-$ROOT/work/catalog-validation-report.json}"

WORK=""
cleanup()
{
    [[ -n "$WORK" ]] && rm -rf "$WORK"
}
trap cleanup EXIT

CATALOG="$INPUT"
case "$INPUT" in
    *.zip)
        command -v unzip >/dev/null 2>&1 || {
            echo "ERROR: unzip is required for a catalog archive" >&2
            exit 1
        }
        WORK="$(mktemp -d)"
        unzip -q "$INPUT" -d "$WORK"
        CATALOG="$WORK"
        ;;
esac

python3 "$ROOT/tools/board_catalog.py" \
    "$CATALOG" \
    --models-dir "$ROOT/profiles/board-models" \
    --vyos-kernel "$VYOS_KERNEL" \
    --report "$REPORT"

echo "Machine-readable report: $REPORT"
