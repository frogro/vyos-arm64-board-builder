#!/usr/bin/env bash
# Validate the installed DTB against the source artifact plus provider transforms.
set -euo pipefail
PROVIDER="${1:?provider required}"
SOURCE="${2:?kernel DTB required}"
INSTALLED="${3:?installed DTB required}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED="$SOURCE"
if [[ "$PROVIDER" == raspberrypi-native ]]; then
    WORK="$(mktemp -d)"
    trap 'rm -rf "$WORK"' EXIT
    dtc -@ -I dts -O dtb -o "$WORK/wifi.dtbo" \
        "$ROOT/tools/firmware-providers/raspberrypi-native/pi5-wifi-mac-overlay.dts"
    fdtoverlay -i "$SOURCE" -o "$WORK/expected.dtb" "$WORK/wifi.dtbo"
    EXPECTED="$WORK/expected.dtb"
fi
cmp -s "$EXPECTED" "$INSTALLED" || {
    echo "ERROR: installed DTB does not match kernel artifact and provider transforms" >&2
    exit 1
}
