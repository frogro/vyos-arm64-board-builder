#!/usr/bin/env python3
"""Opt-in Xorg acceleration using only render devices already granted to container."""
import os
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


def main():
    template = Path('/etc/X11/xorg.conf').read_text()
    nodes = [p for p in Path('/dev/dri').glob('renderD*') if stat.S_ISCHR(p.stat().st_mode)]
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
