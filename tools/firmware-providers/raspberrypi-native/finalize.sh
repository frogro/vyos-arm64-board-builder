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

cp "$ARTIFACTS/Image" "$FIRMWARE_MNT/vmlinuz"
cp "$VERSION_DIR/initrd.img" "$FIRMWARE_MNT/initrd.img"
cp "$DTB" "$FIRMWARE_MNT/$(basename "$BOOT_FDT_FILE")"

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

# Put the authoritative direct-kernel handoff in a final [all] section so it
# cannot accidentally inherit a preceding model-specific section.
config += f"""

[all]
arm_64bit=1
kernel=vmlinuz
initramfs initrd.img followkernel
device_tree={dtb_name}
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
    "$(basename "$BOOT_FDT_FILE")"
do
    [[ -s "$FIRMWARE_MNT/$required" ]] || {
        echo "ERROR: Raspberry Pi final boot payload missing: $required" >&2
        exit 1
    }
done

sync
echo "Finalized Raspberry Pi direct-kernel boot payload for $BOARD"
