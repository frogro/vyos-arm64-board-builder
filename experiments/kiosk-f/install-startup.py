#!/usr/bin/env python3
"""Stage the experimental kiosk startup companion into an explicit rootfs.

Does not activate services, change native container configuration or copy secrets.
Run again for every new image; staging files alone is not an update integration.
"""
import argparse
from pathlib import Path
import re

SOURCE = Path(__file__).resolve().parent
MARKER = '# Managed by VyARM experimental kiosk startup installer\n'


def install(root, name):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,62}', name):
        raise ValueError('Invalid container name')
    root = Path(root).resolve(strict=True)
    files = {
        'usr/local/libexec/vyos-kiosk-wait-addresses': (
            (SOURCE / 'systemd/wait-container-addresses.py').read_bytes(), 0o755),
        f'etc/systemd/system/vyos-container-{name}.service.d/kiosk-retry.conf': (
            (MARKER + '[Unit]\nStartLimitIntervalSec=0\n\n[Service]\n'
             'RestartSec=5s\n'
             f'ExecStartPre=/usr/local/libexec/vyos-kiosk-wait-addresses {name}\n').encode(), 0o644),
    }
    # Check every destination before writing anything. Never follow a staged
    # rootfs symlink to the build host or overwrite an unrelated customization.
    for rel, (data, _) in files.items():
        path = root / rel
        for component in [path, *path.parents]:
            if component == root:
                break
            if component.is_symlink():
                raise ValueError(f'Refusing symlink destination: {component}')
        if path.exists() and path.read_bytes() != data:
            if rel.endswith('.conf') and not path.read_bytes().startswith(MARKER.encode()):
                raise ValueError(f'Unmanaged drop-in exists: {path}')
            if not rel.endswith('.conf'):
                raise ValueError(f'Different helper exists; review before replacing: {path}')
    for rel, (data, mode) in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(mode)
    return list(files)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rootfs', required=True, type=Path)
    parser.add_argument('--container', required=True)
    args = parser.parse_args()
    try:
        for installed in install(args.rootfs, args.container):
            print(installed)
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')
