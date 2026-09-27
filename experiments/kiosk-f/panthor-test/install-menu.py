#!/usr/bin/env python3
"""Add an optional test-kernel menu entry without changing the GRUB default."""
import hashlib
from pathlib import Path
import re
import shutil

PAYLOAD = Path('/usr/share/vyarm/panthor-test')

def render(template, version, release):
    if not re.fullmatch(r'[A-Za-z0-9_.+-]+', version):
        raise ValueError('Unsupported image name')
    if release != '6.18.50-vyos-panthor-cache-test':
        raise ValueError('Unexpected test release')
    base = f'/boot/{version}'
    required = [f'linux "{base}/vmlinuz"', f'initrd "{base}/initrd.img"',
                f'devicetree "{base}/dtb/rockchip/rk3588-rock-5b.dtb"']
    if any(template.count(x) != 1 for x in required) or template.count('menuentry ') != 1:
        raise ValueError('Unrecognized installed-image GRUB template')
    entry_id = 'vyarm-panthor-' + hashlib.sha256(version.encode()).hexdigest()[:16]
    text, count = re.subn(r'^menuentry .*\{',
        f'menuentry "{version} - Panthor cache TEST (optional)" --id {entry_id} {{',
        template, count=1, flags=re.MULTILINE)
    if count != 1:
        raise ValueError('Missing menu header')
    for old, new in zip(required, [f'linux "{base}/panthor-test/Image"',
                                  f'initrd "{base}/panthor-test/initrd.img"',
                                  f'devicetree "{base}/panthor-test/board.dtb"']):
        text = text.replace(old, new)
    # A later image removal must not leave a selectable broken entry.
    return f'if [ -f "{base}/panthor-test/Image" ]; then\n' + text + 'fi\n'

def main():
    cmdline = Path('/proc/cmdline').read_text().split()
    versions = [x.removeprefix('vyos-union=/boot/') for x in cmdline if x.startswith('vyos-union=/boot/')]
    if len(versions) != 1:
        raise ValueError('Installed VyOS image required')
    version = versions[0]
    release = (PAYLOAD / 'kernel.release').read_text().strip()
    if not (Path('/lib/modules') / release).is_dir():
        raise ValueError('Matching test modules missing')
    grub = Path('/boot/grub/grub.cfg.d')
    # render validates version before any version-dependent filesystem writes.
    if not re.fullmatch(r'[A-Za-z0-9_.+-]+', version):
        raise ValueError('Unsupported image name')
    template = (grub / 'vyos-versions' / f'{version}.cfg').read_text()
    text = render(template, version, release)
    dest = Path('/boot') / version / 'panthor-test'
    dest.mkdir(exist_ok=True)
    for name in ['Image', 'initrd.img', 'board.dtb']:
        tmp = dest / (name + '.new')
        shutil.copyfile(PAYLOAD / name, tmp)
        tmp.replace(dest / name)
    output = grub / '45-vyarm-panthor-autoload.cfg'
    tmp = output.with_suffix('.new')
    tmp.write_text(text)
    tmp.replace(output)
    print('Optional Panthor entry installed; saved default and normal entry unchanged')

if __name__ == '__main__':
    main()
