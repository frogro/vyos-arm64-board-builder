#!/usr/bin/env bash
set -euo pipefail

USAGE="Usage: $0 <board> <firmware-mount> <version-dir> <artifacts>"
USAGE+=" <grub-version-cfg> <manifest>"

BOARD="${1:?$USAGE}"
FIRMWARE_MNT="${2:?$USAGE}"
VERSION_DIR="${3:?$USAGE}"
ARTIFACTS="${4:?$USAGE}"
GRUB_VERSION_CFG="${5:?$USAGE}"
MANIFEST="${6:?$USAGE}"
PROVIDER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[[ -s "$MANIFEST" ]] || {
    echo "ERROR: boot manifest missing: $MANIFEST" >&2
    exit 1
}

# Every finalizer consumes the normalized provider contract explicitly rather
# than depending on unexported variables in its parent shell.
# shellcheck disable=SC1090
source "$MANIFEST"

: "${BOOT_FDT_FILE:?BOOT_FDT_FILE missing from manifest}"

DTB="$ARTIFACTS/dtb/$BOOT_FDT_FILE"
[[ -s "$ARTIFACTS/Image" && -s "$VERSION_DIR/initrd.img" && -s "$DTB" ]] || {
    echo "ERROR: Raspberry Pi kernel/initramfs/DTB payload incomplete" >&2
    exit 1
}

for cmd in dtc fdtoverlay fdtget; do
    command -v "$cmd" >/dev/null 2>&1 || {
        echo "ERROR: Raspberry Pi finalizer requires $cmd" >&2
        exit 1
    }
done

cp "$ARTIFACTS/Image" "$FIRMWARE_MNT/vmlinuz"
cp "$VERSION_DIR/initrd.img" "$FIRMWARE_MNT/initrd.img"

FIRMWARE_DTB="$FIRMWARE_MNT/$(basename "$BOOT_FDT_FILE")"
D0_SOURCE="$PROVIDER_DIR/bcm2712d0-mainline-overlay.dts"
WIFI_MAC_SOURCE="$PROVIDER_DIR/pi5-wifi-mac-overlay.dts"

[[ -s "$D0_SOURCE" && -s "$WIFI_MAC_SOURCE" ]] || {
    echo "ERROR: Raspberry Pi provider overlays are missing" >&2
    exit 1
}

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

D0_OVERLAY="$WORK/bcm2712d0.dtbo"
WIFI_MAC_OVERLAY="$WORK/pi5-wifi-mac.dtbo"
MERGED_DTB="$WORK/bcm2712-rpi-5-b.merged.dtb"

dtc -@ -I dts -O dtb -o "$D0_OVERLAY" "$D0_SOURCE"
dtc -@ -I dts -O dtb -o "$WIFI_MAC_OVERLAY" "$WIFI_MAC_SOURCE"

# Add the standard Raspberry Pi firmware MAC hand-off metadata to the
# mainline DTB before the VideoCore firmware processes it. A zero value is
# intentional: firmware replaces it with the board-specific OTP address.
fdtoverlay \
    -i "$DTB" \
    -o "$MERGED_DTB" \
    "$WIFI_MAC_OVERLAY"

mv "$MERGED_DTB" "$FIRMWARE_DTB"

[[ "$(fdtget -t bx \
    "$FIRMWARE_DTB" \
    /soc@107c000000/mmc@1100000/wifi@1 \
    local-mac-address)" == "0 0 0 0 0 0" ]] || {
    echo "ERROR: Raspberry Pi WLAN MAC placeholder is invalid" >&2
    exit 1
}

[[ "$(fdtget -t s "$FIRMWARE_DTB" /aliases wifi0)" == \
   "/soc@107c000000/mmc@1100000/wifi@1" ]] || {
    echo "ERROR: Raspberry Pi wifi0 firmware alias is invalid" >&2
    exit 1
}

fdtget "$FIRMWARE_DTB" /__overrides__ wifiaddr >/dev/null

# Validate the reduced D0 compatibility overlay against the exact generated
# mainline DTB. The full downstream overlay also targets downstream-only HDMI
# and DMA labels, which is why it cannot be applied to this DTB.
fdtoverlay \
    -i "$FIRMWARE_DTB" \
    -o "$WORK/d0-validation.dtb" \
    "$D0_OVERLAY"

mkdir -p "$FIRMWARE_MNT/overlays"
install -m 0644 "$D0_OVERLAY" "$FIRMWARE_MNT/overlays/bcm2712d0.dtbo"
touch "$FIRMWARE_MNT/overlays/README"

python3 - \
    "$FIRMWARE_MNT/config.txt" \
    "$FIRMWARE_MNT/cmdline.txt" \
    "$GRUB_VERSION_CFG" \
    "$(basename "$BOOT_FDT_FILE")" <<'PY'
from pathlib import Path
import re
import sys

config_path, cmdline_path, grub_path = map(Path, sys.argv[1:4])
dtb_name = Path(sys.argv[4]).name
config = config_path.read_text(encoding="utf-8", errors="replace")

# Make the finalizer idempotent when an image is rebuilt from an already
# modified firmware template.
config = re.sub(
    r"(?m)^[ \t]*dtoverlay=bcm2712d0[ \t]*\n?",
    "",
    config,
)

# Put the authoritative direct-kernel handoff in a final [all] section so it
# cannot accidentally inherit a preceding model-specific section.
config += f"""

[all]
arm_64bit=1
kernel=vmlinuz
initramfs initrd.img followkernel
device_tree={dtb_name}
dtoverlay=bcm2712d0
"""
config_path.write_text(config, encoding="utf-8")

grub = grub_path.read_text(encoding="utf-8", errors="replace")

# The rendered linux line expands ${boot_opts} at GRUB runtime.  Its initial
# concrete value is recorded in the same per-version file and is the stable
# source for a firmware-direct cmdline.
match = re.search(r'^\s*set boot_opts="([^$\"]+)"\s*$', grub, re.MULTILINE)
if not match:
    raise SystemExit("ERROR: no concrete VyOS boot_opts found for Pi cmdline")
arguments = match.group(1).strip()
if "boot=live" not in arguments or "vyos-union=" not in arguments:
    raise SystemExit("ERROR: VyOS live-boot arguments are incomplete")
arguments += " console=ttyAMA10,115200 console=tty0"
cmdline_path.write_text(arguments + "\n", encoding="utf-8")
PY

for required in \
    config.txt \
    cmdline.txt \
    vmlinuz \
    initrd.img \
    "$(basename "$BOOT_FDT_FILE")" \
    overlays/bcm2712d0.dtbo
do
    [[ -s "$FIRMWARE_MNT/$required" ]] || {
        echo "ERROR: Raspberry Pi final boot payload missing: $required" >&2
        exit 1
    }
done

sync
echo "Finalized Raspberry Pi direct-kernel boot payload for $BOARD"
