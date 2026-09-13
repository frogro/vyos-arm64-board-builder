#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEMP="$(mktemp -d)"
trap 'rm -rf "$TEMP"' EXIT
git init -q "$TEMP/upstream"
git -C "$TEMP/upstream" -c user.name=Test -c user.email=test@example.invalid commit -q --allow-empty -m baseline
PIN="$(git -C "$TEMP/upstream" rev-parse HEAD)"
git -C "$TEMP/upstream" -c user.name=Test -c user.email=test@example.invalid commit -q --allow-empty -m newer
git -C "$TEMP/upstream" branch rolling
ROOT_DIR="$TEMP/builder"
VYOS_BUILD_REPO="$TEMP/upstream"
source "$ROOT/sources/vyos.sh"
info() { :; }
die() { echo "$*" >&2; exit 1; }
VYOS_REF=rolling
vyos_fetch >/dev/null 2>&1
[[ "$(git -C "$ROOT_DIR/cache/vyos-build" rev-parse HEAD)" != "$PIN" ]]
VYOS_REF="$PIN"
vyos_fetch >/dev/null 2>&1
[[ "$(git -C "$ROOT_DIR/cache/vyos-build" rev-parse HEAD)" == "$PIN" ]]
echo 'PASS: exact VyOS commit pin overrides moving rolling branch'
