#!/usr/bin/env python3
"""Manage the opt-in CSC prerequisite while a native Wayland remote policy exists."""
import json
from pathlib import Path
import signal
import time

PARAM = Path('/sys/module/rockchip_rga/parameters/experimental_full_csc')
SAVED = Path('/run/vyos-kiosk-csc-before')

def requested():
    for policy in Path('/run/vyos-kiosk').glob('*/sunshine.json'):
        try:
            p = json.loads(policy.read_text())
            q = Path('/run/containers/systemd') / f'vyos-container-{policy.parent.name}.container'
            text = q.read_text()
            if (p.get('access') == 'enabled' and
                    'Environment=SUNSHINE_VYARM_DIRECT_RGA="1"' in text):
                return True
        except (OSError, ValueError):
            continue
    return False

def restore():
    if SAVED.exists() and PARAM.exists():
        before = SAVED.read_text().strip()
        if before in ('N', 'Y', '0', '1'):
            PARAM.write_text(before)
        SAVED.unlink()

def main():
    stopped = False
    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        while not stopped:
            if requested() and PARAM.exists():
                if not SAVED.exists():
                    with SAVED.open('x') as f:
                        f.write(PARAM.read_text())
                if PARAM.read_text().strip() not in ('Y', '1'):
                    PARAM.write_text('Y')
            else:
                restore()
            time.sleep(1)
    finally:
        restore()

if __name__ == '__main__':
    main()
