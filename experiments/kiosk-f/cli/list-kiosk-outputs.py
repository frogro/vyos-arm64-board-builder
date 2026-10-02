#!/usr/bin/env python3
"""Read X11 output names from one kiosk; never infer them from DRM names.

Invoked by native administrator-only config completion with sudo -n, like
upstream container image completion. No new sudo/role rules are installed.
Unavailable desktop or permissions yield only auto and never start a container.
"""
import re
import subprocess
import sys


def connected(text):
    return sorted(set(re.findall(r'^([A-Za-z0-9][A-Za-z0-9_.:-]*) connected(?: |$)', text, re.M)))


def candidates(name, run=subprocess.run):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,62}', name):
        return ['auto']
    try:
        result = run(['podman', 'exec', '--user', 'kiosk',
                      '--env', 'DISPLAY=:0', '--env', 'XAUTHORITY=/run/kiosk/Xauthority',
                      name, 'xrandr', '--query'],
                     capture_output=True, text=True, timeout=2, check=False)
        if result.returncode == 0:
            return ['auto', *[x for x in connected(result.stdout) if x != 'auto']]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ['auto']


if __name__ == '__main__':
    print(' '.join(candidates(sys.argv[1] if len(sys.argv) == 2 else '')))
