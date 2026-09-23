#!/usr/bin/env python3
"""Prepare an X11 or optional DRM Wayland touch kiosk; print commands unless --apply is given."""
import argparse
import datetime
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import subprocess

API = '/bin/cli-shell-api'
META = Path('/usr/share/vyos-arm64-board-builder/kiosk-runtime/runtime.json')


def commands(name, image, card, inputs, backend="x11", media_devices=()):
    if backend not in ("x11", "wayland"):
        raise ValueError("Invalid display backend")
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,39}', name):
        raise ValueError('Invalid container name')
    if not re.fullmatch(r'localhost/vyarm-kiosk:[A-Za-z0-9_.-]+', image):
        raise ValueError('Invalid versioned runtime tag')
    if not re.fullmatch(r'/dev/dri/card[0-9]+', card):
        raise ValueError('Invalid display device')
    prefix = ['container', 'name', name]
    settings = [['container', 'network', name, 'prefix', '10.89.50.0/24']]
    settings += [prefix + row for row in [
        ['image', image], ['network', name], ['memory', '2048'],
        ['cpu-quota', '4'], ['shared-memory', '256'], ['restart', 'on-failure'],
        ['capability', 'sys-admin'], ['kiosk', 'url', 'file:///opt/kiosk/input-test.html'],
        ['kiosk', 'output', 'auto'], ['kiosk', 'rotation', '0'],
        ['kiosk', 'graphics', 'software'], ['kiosk', 'video-decode', 'software']]]
    devices = [('display', card, '/dev/dri/card0'),
               ('console-control', '/dev/tty0', '/dev/tty0'),
               ('console', '/dev/tty8', '/dev/tty8')]
    if backend == 'wayland':
        settings.append(prefix + ['kiosk', 'display-backend', 'wayland'])
        for i, path in enumerate(media_devices):
            if not re.fullmatch(r'/dev/(dri/renderD[0-9]+|video[0-9]+|media[0-9]+)', path):
                raise ValueError('Invalid media device')
            devices.append((f'media-{i}', path, path))
    for i, (source, target) in enumerate(inputs):
        if not re.fullmatch(r'/dev/input/by-(id|path)/[^/\s]+', source) or not re.fullmatch(r'/dev/input/event[0-9]+', target):
            raise ValueError('Invalid stable input mapping')
        devices.append((f'input-{i}', source, target))
    for label, source, dest in devices:
        for key, value in [('source', source), ('destination', dest)]:
            settings.append(prefix + ['device', label, key, value])
    for label, source, dest, mode in [('udev', '/run/udev', '/run/udev', 'ro'),
                                    ('state', f'/config/{name}/state', '/state', 'rw')]:
        for key, value in [('source', source), ('destination', dest), ('mode', mode)]:
            settings.append(prefix + ['volume', label, key, value])
    return ['set ' + shlex.join(row) for row in settings]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', default='kiosk')
    parser.add_argument('--display-backend', choices=['x11', 'wayland'], default='x11')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Run with sudo; no changes are made without --apply')
    meta = json.loads(META.read_text())
    # Refuse replacement on updates or repeated setup, including any existing
    # container network of the same name. Never import the live router config.
    for node in ['name', 'network']:
        if subprocess.run([API, 'existsActive', 'container', node, args.name]).returncode == 0:
            raise ValueError(f'Existing container {node} {args.name}; keep it and use the normal CLI')
    subnet = ipaddress.ip_network('10.89.50.0/24')
    routes = json.loads(subprocess.check_output(['ip', '-j', '-4', 'route', 'show', 'table', 'all']))
    if any(r.get('dst', 'default') != 'default' and subnet.overlaps(ipaddress.ip_network(r['dst'], strict=False)) for r in routes):
        raise ValueError('10.89.50.0/24 overlaps an existing route; configure network manually')
    cards = sorted({str(Path('/dev/dri') / re.match(r'(card[0-9]+)-', p.parent.name)[1])
                    for p in Path('/sys/class/drm').glob('card*-*/status')
                    if p.read_text().strip() == 'connected'})
    if len(cards) != 1:
        raise ValueError('Exactly one connected display card required; connect display or configure manually')
    inputs, seen = [], set()
    for p in sorted(Path('/dev/input/by-id').glob('*event*')):
        target = str(p.resolve())
        if p.is_char_device() and target not in seen:
            inputs.append((str(p), target)); seen.add(target)
    media_devices = []
    if args.display_backend == 'wayland':
        import fcntl, struct
        renders = sorted(Path('/dev/dri').glob('renderD*'))
        if len(renders) != 1:
            raise ValueError('Exactly one render device required; otherwise configure manually')
        media_devices = [str(renders[0])]
        # Select decoder queues by compressed input formats, never board/video numbers.
        for node in sorted(Path('/dev').glob('video*')):
            try:
                fd = os.open(node, os.O_RDWR | os.O_NONBLOCK)
                formats = set()
                try:
                    for queue in (2, 10):
                        for index in range(64):
                            fmt = bytearray(64)
                            struct.pack_into('II', fmt, 0, index, queue)
                            try: fcntl.ioctl(fd, 0xc0405602, fmt, True)
                            except OSError: break
                            formats.add(bytes(fmt[44:48]))
                finally: os.close(fd)
                if formats & {b'S264', b'S265', b'VP9F', b'AV1F'}:
                    media_devices.append(str(node))
            except OSError: continue
        media_devices += [str(p) for p in sorted(Path('/dev').glob('media*')) if p.is_char_device()]
    lines = commands(args.name, meta['image'], cards[0], inputs, args.display_backend, media_devices)
    subprocess.run(['podman', 'image', 'exists', meta['image']], check=True)
    print('\n'.join(['configure', *lines, 'commit', 'save', 'exit']), flush=True)
    if not args.apply:
        return
    state = Path('/config') / args.name / 'state'
    if state.exists():
        raise ValueError('State directory already exists; refusing first-install setup')
    backup = Path('/config') / ('config.boot.before-kiosk-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    with backup.open('xb') as f:
        os.chmod(backup, 0o600)
        f.write(Path('/config/config.boot').read_bytes())
    state.mkdir(parents=True)
    script = 'source /opt/vyatta/etc/functions/script-template\nconfigure\n'
    script += '\n'.join(line + ' || exit 1' for line in lines)
    script += '\ncommit || exit 1\nsave || exit 1\nexit\n'
    subprocess.run(['runuser', '-u', 'vyos', '--', '/bin/vbash'], input=script, text=True, check=True)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
