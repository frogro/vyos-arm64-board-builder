#!/usr/bin/env python3
"""Experimental X11 display configuration; no host device access is granted here."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlsplit

ROTATIONS = {'0': 'normal', '90': 'left', '180': 'inverted', '270': 'right'}
MATRICES = {
    '0': [1, 0, 0, 0, 1, 0, 0, 0, 1],
    '90': [0, -1, 1, 1, 0, 0, 0, 0, 1],
    '180': [-1, 0, 1, 0, -1, 1, 0, 0, 1],
    '270': [0, 1, 0, -1, 0, 1, 0, 0, 1],
}


def settings(env):
    rotation = env.get('KIOSK_ROTATION', '0')
    output = env.get('KIOSK_OUTPUT', 'auto')
    url = env.get('KIOSK_URL', 'file:///opt/kiosk/input-test.html')
    if rotation not in ROTATIONS:
        raise ValueError('KIOSK_ROTATION must be 0, 90, 180 or 270')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]*', output):
        raise ValueError('Invalid KIOSK_OUTPUT')
    if any(ord(c) < 32 or ord(c) == 127 for c in url):
        raise ValueError('URL contains control characters')
    parsed = urlsplit(url)
    if not ((parsed.scheme in ('http', 'https') and parsed.hostname) or
            (parsed.scheme == 'file' and not parsed.netloc and parsed.path.startswith('/'))):
        raise ValueError('KIOSK_URL must be an absolute http(s) or local file URL')
    return rotation, output, url


def command(args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=10).stdout


def outputs(text):
    return [(m[1], bool(m[2])) for m in re.finditer(
        r'^([\w.:-]+) connected( primary)?(?: |$)', text, re.M)]


def select_output(text, requested):
    found = outputs(text)
    if requested != 'auto':
        if requested not in [name for name, _ in found]:
            raise ValueError(f'Display {requested} is not connected')
        return requested
    primary = [name for name, flag in found if flag]
    if len(primary) == 1:
        return primary[0]
    if len(found) == 1:
        return found[0][0]
    raise ValueError('Select KIOSK_OUTPUT explicitly: no unique connected/primary display')


def geometry(text, output):
    screen = re.search(r'current (\d+) x (\d+)', text)
    match = re.search(r'^' + re.escape(output) + r' connected(?: primary)? (\d+)x(\d+)\+(\d+)\+(\d+)', text, re.M)
    if not screen or not match:
        raise ValueError('Cannot determine active display geometry')
    return tuple(map(int, match.groups() + screen.groups()))


def touch_matrix(rotation, geom):
    w, h, x, y, sw, sh = geom
    if min(w, h, sw, sh) <= 0:
        raise ValueError('Invalid display size')
    a = MATRICES[rotation]
    return [w/sw*a[0], w/sw*a[1], w/sw*a[2]+x/sw,
            h/sh*a[3], h/sh*a[4], h/sh*a[5]+y/sh, 0, 0, 1]


def write_status(data):
    path = Path('/run/kiosk/display.json')
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data) + '\n')
    tmp.replace(path)


def configure():
    rotation, requested, _ = settings(os.environ)
    output = select_output(command(['xrandr', '--query']), requested)
    # Preserve the existing mode/refresh. Xorg swaps logical dimensions on rotation.
    command(['xrandr', '--output', output, '--rotate', ROTATIONS[rotation]])
    geom = geometry(command(['xrandr', '--query']), output)
    write_status(dict(output=output, rotation=int(rotation), geometry=geom,
                      touch_devices=[], touch_note='Only exposed physical touchscreens are mapped'))
    print(f'Kiosk display {output}: rotation={rotation}, logical={geom[0]}x{geom[1]}', flush=True)
    return output, rotation


def touch_devices():
    found = []
    for device in command(['xinput', '--list', '--id-only']).split():
        if not device.isdecimal():
            continue
        props = command(['xinput', '--list-props', device])
        node = re.search(r'Device Node \(\d+\):\s+"(/dev/input/event\d+)"', props)
        if not node or 'Coordinate Transformation Matrix' not in props:
            continue
        info = command(['udevadm', 'info', '--query=property', '--name', node[1]])
        values = dict(line.split('=', 1) for line in info.splitlines() if '=' in line)
        if values.get('ID_INPUT_TOUCHSCREEN') == '1':
            found.append((device, node[1]))
    return found


def watch():
    rotation, requested, _ = settings(os.environ)
    previous = None
    last_error = None
    while True:
        try:
            text = command(['xrandr', '--query'])
            output = select_output(text, requested)
            geom = geometry(text, output)
            devices = touch_devices()
            signature = (output, geom, tuple(devices))
            if signature != previous:
                matrix = [str(v) for v in touch_matrix(rotation, geom)]
                for device, _ in devices:
                    command(['xinput', '--set-prop', device, 'Coordinate Transformation Matrix', *matrix])
                write_status(dict(output=output, rotation=int(rotation), geometry=geom,
                                  touch_devices=devices, touch_note='Only exposed physical touchscreens are mapped'))
                previous = signature
            last_error = None
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            if str(error) != last_error:
                print(f'Kiosk touch mapping: {error}', flush=True)
                last_error = str(error)
        time.sleep(2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['validate', 'configure', 'watch'])
    action = parser.parse_args().action
    try:
        if action == 'validate':
            settings(os.environ)
        elif action == 'configure':
            configure()
        else:
            watch()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit(f'Kiosk display configuration failed: {error}')
