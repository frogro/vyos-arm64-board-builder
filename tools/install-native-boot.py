#!/usr/bin/env python3
"""Install guarded native boot lifecycle hooks in the assembled VyOS rootfs."""
import argparse
import ast
import json
from pathlib import Path
import shutil


def patch_grub(path):
    text = path.read_text()
    marker = '# VyOS ARM64 native boot lifecycle hooks'
    if marker in text:
        return
    tree = ast.parse(text)
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    required = {'version_add', 'version_del', 'set_default', 'set_console_type', 'set_serial_console'}
    if not required <= functions:
        raise RuntimeError('Unsupported VyOS GRUB API for native lifecycle hooks')
    text += '\n\n' + marker + '\nfrom vyos.system.board_boot import decorate as _native_boot\n'
    # set_kernel_cmdline_options calls version_add; wrapping both would recurse
    # into the lock. Only wrap the primitive mutations.
    for function in sorted(required):
        text += f'{function} = _native_boot({function})\n'
    ast.parse(text)
    path.write_text(text)


def patch_manager(path):
    text = path.read_text()
    if '# Native boot deletion ordering' in text:
        return
    old = '        rmtree(version_path)\n        grub.version_del(image_name, persistence_storage)'
    new = '''        # Native boot deletion ordering: publish menu before removing rootfs.
        if Path('/usr/share/vyos-arm64-board-builder/boot-provider.json').is_file():
            grub.version_del(image_name, persistence_storage)
            rmtree(version_path)
        else:
            rmtree(version_path)
            grub.version_del(image_name, persistence_storage)'''
    if text.count(old) != 1:
        raise RuntimeError('Unsupported VyOS delete-image implementation')
    text = text.replace(old, new)
    # Upstream rename changes default before moving files; that intermediate
    # state cannot be made bootable. Reject until a transactional rename exists.
    anchor = "    if name_old == image.get_running_image():"
    if text.count(anchor) != 1:
        raise RuntimeError('Unsupported VyOS rename-image implementation')
    text = text.replace(anchor, "    if Path('/usr/share/vyos-arm64-board-builder/boot-provider.json').is_file():\n        exit('Native boot image rename is not supported; add the ISO under the desired name instead')\n\n" + anchor)
    ast.parse(text)
    path.write_text(text)


def install(root, metadata):
    profile = root / 'usr/share/vyos-arm64-board-builder'
    profile.mkdir(parents=True, exist_ok=True)
    (profile / 'boot-provider.json').write_text(json.dumps(metadata, indent=2) + '\n')
    candidates = list(root.glob('usr/lib/python3*/dist-packages/vyos/system/grub.py'))
    if len(candidates) != 1:
        raise RuntimeError('Cannot locate unique VyOS grub.py')
    patch_grub(candidates[0])
    shutil.copyfile(Path(__file__).parent / 'firmware-providers/armbian-uboot/board_boot.py', candidates[0].with_name('board_boot.py'))
    if metadata.get('firmware_provider') == 'raspberrypi-native':
        shutil.copyfile(Path(__file__).parent / 'firmware-providers/raspberrypi-native/board_boot_rpi.py', candidates[0].with_name('board_boot_rpi.py'))
    patch_manager(root / 'usr/libexec/vyos/op_mode/image_manager.py')
    flavor_path = root / 'usr/share/vyos/flavor.json'
    flavor = json.loads(flavor_path.read_text())
    import re
    match = re.fullmatch(r'(ttyS|ttyAMA)([0-9]+)', metadata['console'])
    if not match: raise RuntimeError('Invalid native serial console')
    flavor.update(console_type=match[1], console_num=match[2], console_speed=str(metadata['baud']))
    flavor_path.write_text(json.dumps(flavor) + '\n')
    diagnostics = root / 'usr/local/sbin/vyos-board-diagnostics'
    diagnostics.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(__file__).parent / 'common-firstboot/board-diagnostics.sh', diagnostics)
    diagnostics.chmod(0o755)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('rootfs', type=Path)
    parser.add_argument('metadata', type=Path)
    args = parser.parse_args()
    install(args.rootfs, json.loads(args.metadata.read_text()))
