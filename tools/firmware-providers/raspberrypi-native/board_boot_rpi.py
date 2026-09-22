"""Experimental Pi FAT handoff, driven by the native VyOS image selection.

Firmware/EEPROM are deliberately not updated. Complete immutable OS payloads
are flushed before a single config.txt replacement. This is not a guarantee
against FAT corruption during physical power loss.
"""
import hashlib
import os
from pathlib import Path
import re
import shutil
import tempfile
from uuid import NAMESPACE_URL, uuid5

BEGIN = '# BEGIN VYOS MANAGED PI BOOT'
END = '# END VYOS MANAGED PI BOOT'


def sync(root, firmware, metadata, common):
    root, firmware = Path(root), Path(firmware)
    if (metadata.get('board'), metadata.get('firmware_provider'), metadata.get('update_provider'), metadata.get('firmware_partition')) != ('raspberry-pi-5', 'raspberrypi-native', 'firmware-files', 1):
        raise RuntimeError('Unsupported Pi boot contract')
    variables = common.grub_vars(root)
    configs = [p for p in (root / common.VERSIONS).glob('*.cfg')
               if 'uuid5-' + str(uuid5(NAMESPACE_URL, p.stem)) == variables.get('default')]
    if len(configs) != 1:
        raise RuntimeError('Selected Pi image is not installed')
    cfg = configs[0]
    version = common.name(cfg.stem)
    directory = root / 'boot' / version
    info = common.read_json(directory / 'board-boot.json')
    for key in ('schema', 'board', 'architecture', 'profile', 'firmware_provider', 'update_provider', 'device_tree', 'firmware_partition'):
        if info.get(key) != metadata.get(key):
            raise RuntimeError(f'Incompatible Pi boot metadata: {key}')
    dtb = common.dtb_path(info.get('device_tree'))
    sources = {'vmlinuz': directory / 'vmlinuz', 'initrd.img': directory / 'initrd.img',
               Path(dtb).name: directory / 'dtb' / dtb,
               'overlays/bcm2712d0.dtbo': directory / 'rpi/bcm2712d0.dtbo'}
    # Retain firmware-template overlays; the selected image supplies its D0
    # overlay. README makes Raspberry Pi firmware apply os_prefix to overlays.
    for source in sorted((firmware / 'overlays').glob('*')):
        if source.is_file() and source.name != 'README':
            sources.setdefault('overlays/' + source.name, source)
    data = {'cmdline.txt': (common.boot_options(cfg, version, info, variables) + '\n').encode(),
            'overlays/README': b'VyOS versioned overlays\n'}
    for target, source in sources.items():
        if not source.is_file() or not source.stat().st_size:
            raise RuntimeError(f'Pi boot payload missing: {source}')
        data[target] = source.read_bytes()
    digest = hashlib.sha256()
    for target, content in sorted(data.items()):
        digest.update(target.encode() + b'\0' + hashlib.sha256(content).digest())
    token = digest.hexdigest()
    destination = firmware / 'vyos-boot/payloads' / token
    if destination.exists():
        if any(not (destination / p).is_file() or (destination / p).read_bytes() != content for p, content in data.items()):
            raise RuntimeError('Cached Pi boot payload is incomplete or corrupt')
    else:
        if shutil.disk_usage(firmware).free < sum(map(len, data.values())) + 1024 * 1024:
            raise RuntimeError('Pi FAT partition has insufficient space; boot selection unchanged')
        destination.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='.stage-', dir=destination.parent))
        try:
            for target, content in data.items():
                common.atomic_write(stage / target, content)
            os.replace(stage, destination)
            os.sync()
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    config_path = firmware / 'config.txt'
    previous = config_path.read_bytes()
    config = previous.decode('utf-8')
    if config.count(BEGIN) != config.count(END) or config.count(BEGIN) > 1:
        raise RuntimeError('Malformed managed Pi boot configuration')
    config = re.sub(re.escape(BEGIN) + r'.*?' + re.escape(END) + r'\n?', '', config, flags=re.S)
    config = re.sub(r'(?m)^\s*dtoverlay=bcm2712d0\s*$', '', config)
    config += (f'\n{BEGIN}\n[all]\narm_64bit=1\nos_prefix=vyos-boot/payloads/{token}/\n'
               f'kernel=vmlinuz\ninitramfs initrd.img followkernel\ndevice_tree={Path(dtb).name}\n'
               f'cmdline=cmdline.txt\noverlay_prefix=overlays/\ndtoverlay=bcm2712d0\n{END}\n')
    # Retain a manual recovery copy and all older payloads for the experimental
    # phase. No automatic garbage collection until hardware validation.
    common.atomic_write(firmware / 'vyos-boot/config.previous.txt', previous)
    try:
        common.atomic_write(config_path, config.encode())
    except Exception:
        common.atomic_write(config_path, previous)
        raise
