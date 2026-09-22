#!/usr/bin/env python3
"""Show selection state without claiming that process liveness proves a picture."""
import json
import subprocess
from pathlib import Path


def main():
    service = subprocess.run(['systemctl', 'is-active', 'vyos-kvm-video'],
                             capture_output=True, text=True, timeout=5)
    print('Video service: ' + service.stdout.strip())
    try:
        state = json.loads(Path('/run/vyos-kvm-over-ip/capture.json').read_text())
    except (OSError, ValueError):
        print('No capture selection recorded for this boot.')
        return
    print('Last selection (not a live signal measurement):')
    for label, key in [('Device', 'device'), ('Name', 'name'), ('Source provider', 'source'),
                       ('Signal at selection', 'signal'), ('Backend', 'backend'),
                       ('Pixel format', 'format'), ('Requested resolution', 'requested_resolution'),
                       ('Requested frame rate', 'requested_framerate')]:
        print(f"  {label}: {state.get(key) or 'automatic'}")
    print('Pipeline processes:')
    subprocess.run(['systemctl', 'status', 'vyos-kvm-video', '--no-pager', '--lines=0'], timeout=5)


if __name__ == '__main__':
    main()
