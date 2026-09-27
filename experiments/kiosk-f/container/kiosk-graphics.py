#!/usr/bin/env python3
"""Opt-in Xorg acceleration using only render devices already granted to container."""
import os
import pwd
from pathlib import Path
import stat
import sys


def prepare(mode, template, render_nodes):
    if mode not in ('software', 'auto'):
        raise ValueError('KIOSK_GRAPHICS must be software or auto')
    marker = 'Option "AccelMethod" "none"'
    if template.count(marker) != 1:
        raise ValueError('Expected one explicit software AccelMethod in Xorg template')
    accelerated = mode == 'auto' and bool(render_nodes)
    return template.replace(marker, 'Option "AccelMethod" "glamor"') if accelerated else template, accelerated


def supplementary_groups(existing, device_groups):
    # Never grant the root group merely because a device is root-owned.
    return sorted(set(existing) | {gid for gid in device_groups if gid != 0})


def main():
    nodes = [p for p in Path('/dev/dri').glob('renderD*') if stat.S_ISCHR(p.stat().st_mode)]
    if sys.argv[1:] == ['--groups']:
        user = pwd.getpwnam('kiosk')
        existing = os.getgrouplist(user.pw_name, user.pw_gid)
        selected = [p.stat().st_gid for p in nodes] if os.environ.get('KIOSK_GRAPHICS', 'software') == 'auto' else []
        selected += [p.stat().st_gid for p in Path('/dev/snd').glob('*') if p.is_char_device()]
        print(','.join(map(str, supplementary_groups(existing, selected))))
        return
    template = Path('/etc/X11/xorg.conf').read_text()
    text, accelerated = prepare(os.environ.get('KIOSK_GRAPHICS', 'software'), template, nodes)
    target = Path('/run/kiosk/xorg-runtime.conf')
    target.write_text(text)
    print('glamor' if accelerated else 'software')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
