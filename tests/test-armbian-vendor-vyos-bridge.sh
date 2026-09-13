#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/tools/firmware-providers/armbian-uboot/native-env.sh"
FIRMWARE_PROVIDER=armbian-uboot HW_BRANCH=current BOOT_BRANCH=vendor UBOOT_BOOTSCRIPT=boot-rk35xx.cmd:boot.cmd
native_extlinux_enabled
BOOT_BRANCH=current
if native_extlinux_enabled; then exit 1; fi
python3 "$ROOT/tests/test-native-boot.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
python3 - "$ROOT" "$TMP" <<'PY'
import json,sys,subprocess
from pathlib import Path
from uuid import uuid5,NAMESPACE_URL
root, temp = map(Path,sys.argv[1:])
version=temp/'persistence/boot/test-v1'
(version/'dtb/vendor').mkdir(parents=True)
for name in ['vmlinuz','initrd.img','dtb/vendor/board.dtb']:(version/name).write_text('fixture')
meta=dict(schema=1,architecture='arm64',board='example',profile='network',firmware_provider='armbian-uboot',update_provider='uboot-extlinux',device_tree='vendor/board.dtb',console='ttyS2',baud=1500000,firmware_partition=2)
(version/'board-boot.json').write_text(json.dumps(meta))
grub=temp/'persistence/boot/grub/grub.cfg.d';(grub/'vyos-versions').mkdir(parents=True)
cfg=grub/'vyos-versions/test-v1.cfg';cfg.write_text('set boot_opts="boot=live vyos-union=/boot/test-v1"\n')
(grub/'20-vyos-defaults-autoload.cfg').write_text(f'set default="{uuid5(NAMESPACE_URL,"test-v1")}"\n')
manifest=temp/'manifest.env';manifest.write_text('FIRMWARE_PROVIDER=armbian-uboot\nHW_BRANCH=current\nBOOT_BRANCH=vendor\nUBOOT_BOOTSCRIPT=boot-rk35xx.cmd:boot.cmd\n')
fat=temp/'fat';fat.mkdir()
subprocess.run(['bash',str(root/'tools/firmware-providers/armbian-uboot/bootfiles.sh'),'example',str(fat),str(version),str(cfg),str(manifest)],check=True)
assert 'BOOT_IMAGE=/boot/test-v1/vmlinuz' in (fat/'extlinux/extlinux.conf').read_text()
assert 'console=ttyS2,1500000n8' in (fat/'extlinux/extlinux.conf').read_text()
print('PASS initial native bootfiles assembly')
PY
