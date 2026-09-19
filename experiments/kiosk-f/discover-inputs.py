#!/usr/bin/env python3
"""Read-only USB input discovery for the kiosk prototype. No vendor allowlist.

Prints a JSON inventory. Does not mutate VyOS config or grant container access.
Re-run after hotplug; a reconciler must separately handle missing devices and
container restarts. Never treat an event number as a persistent device identity.
"""
import argparse
import json
import pathlib
import subprocess


def discover(include_touch=False):
    aliases = {}
    for directory in ('/dev/input/by-id', '/dev/input/by-path'):
        for entry in sorted(pathlib.Path(directory).glob('*')):
            if entry.is_symlink():
                aliases.setdefault(str(entry.resolve()), str(entry))
    found = []
    for event in sorted(pathlib.Path('/sys/class/input').glob('event*')):
        dev = '/dev/input/' + event.name
        result = subprocess.run(['udevadm', 'info', '--query=property', '--name', dev],
                                capture_output=True, text=True, check=False)
        if result.returncode:
            continue  # Device may have disappeared during enumeration.
        props = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        if props.get('ID_BUS') != 'usb':
            continue
        touch = props.get('ID_INPUT_TOUCHSCREEN') == '1' or props.get('ID_INPUT_TABLET') == '1'
        classes = [role for role, key in [('keyboard', 'ID_INPUT_KEYBOARD'),
                    ('mouse', 'ID_INPUT_MOUSE'), ('touchscreen', 'ID_INPUT_TOUCHSCREEN')]
                   if props.get(key) == '1']
        if not classes or (touch and not include_touch):
            continue
        if not pathlib.Path(dev).exists():
            continue
        found.append({'classes': classes, 'source': aliases.get(dev, dev),
                      'destination': dev, 'stable_path': dev in aliases,
                      'physical_path': props.get('ID_PATH'),
                      'name': (event / 'device/name').read_text().strip()})
    return found

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-touch', action='store_true')
    args = parser.parse_args()
    print(json.dumps(discover(args.include_touch), indent=2))
