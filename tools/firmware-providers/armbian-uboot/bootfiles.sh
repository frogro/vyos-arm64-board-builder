#!/usr/bin/env bash
set -euo pipefail
BOARD="${1:?board}"; EFI_ROOT="${2:?firmware root}"; VERSION_DIR="${3:?version directory}"
GRUB_VERSION_CFG="${4:?GRUB version config}"; MANIFEST="${5:?boot manifest}"
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$MANIFEST"
source "$HERE/native-env.sh"
if ! native_extlinux_enabled; then
    echo "Native extlinux boot bridge not selected"
    exit 0
fi
python3 - "$HERE" "$EFI_ROOT" "$VERSION_DIR" <<'PYBOOT'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import board_boot
firmware, version_dir = map(Path, sys.argv[2:])
metadata = board_boot.read_json(version_dir / 'board-boot.json')
board_boot.atomic_write(firmware / 'vyos-boot/provider.json', (version_dir / 'board-boot.json').read_bytes())
board_boot.sync(version_dir.parent.parent, firmware, metadata)
print('Installed versioned native U-Boot/extlinux boot menu')
PYBOOT
