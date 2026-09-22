#!/usr/bin/env python3
"""Discover V4L2 sources without confusing bridge hardware with host encoders."""
import argparse
import json
import re
import shlex
import subprocess
from pathlib import Path


def query(device, *args):
    try:
        p = subprocess.run(['v4l2-ctl', '-d', str(device), *args],
                           capture_output=True, text=True, timeout=4)
        return p.returncode, p.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 1, ''


def capture_caps(text):
    # The top-level capabilities can include capabilities of sibling nodes.
    caps = text.split('Device Caps', 1)[-1].split('Media Driver Info', 1)[0]
    return 'Video Capture' in caps and 'Memory-to-Memory' not in caps


def choose(candidates, explicit='', previous=''):
    for identity in (explicit, previous):
        if identity:
            for c in candidates:
                if Path(c['device']).resolve() == Path(identity).resolve():
                    return c
            if explicit:
                raise ValueError('Configured source is not an available capture device')
    # Unknown USB signal status must not be represented as confirmed HDMI lock.
    usable = [c for c in candidates if c['signal'] != 'absent']
    if not usable:
        raise ValueError('No capture source with a present or unknown signal')
    return sorted(usable, key=lambda c: (c['signal'] != 'present', c['device']))[0]


def select_format(formats, backend):
    order = (['YUYV', 'UYVY', 'MJPG', 'BGR3', 'RGB3'] if backend == 'ustreamer'
             else ['NV12', 'YUYV', 'UYVY', 'BGR3', 'RGB3'])
    for f in order:
        if f in formats:
            return f
    raise ValueError('No supported capture format for backend ' + backend)


def parse_modes(text):
    modes = {}
    fmt = size = None
    for line in text.splitlines():
        match = re.search(r"\[\d+\]:\s*'([^']+)'", line)
        if match:
            fmt, size = match[1], None
            modes.setdefault(fmt, {})
        match = re.search(r'Size: Discrete (\d+x\d+)', line)
        if match and fmt:
            size = match[1]
            modes[fmt].setdefault(size, [])
        match = re.search(r'Interval: Discrete.*?\(([0-9.]+) fps\)', line)
        if match and fmt and size:
            modes[fmt][size].append(float(match[1]))
    return modes


def compatible_formats(candidate, resolution='', framerate=''):
    detected = candidate.get('detected_fps')
    if framerate and detected and abs(detected-float(framerate)) > max(detected, float(framerate))*0.005:
        return []
    formats = []
    for fmt in candidate['formats']:
        sizes = candidate.get('modes', {}).get(fmt, {})
        if sizes:
            if resolution and resolution not in sizes:
                continue
            rates = sizes[resolution] if resolution else [r for values in sizes.values() for r in values]
            if framerate and rates and not any(abs(r-float(framerate)) <= max(r, float(framerate))*0.005 for r in rates):
                continue
        formats.append(fmt)
    return formats


def validate_size(candidate, fmt, resolution):
    if not resolution or candidate['signal'] == 'absent':
        return
    if candidate.get('detected_size') and resolution != candidate['detected_size']:
        raise ValueError('Requested resolution differs from HDMI signal; change the source resolution')
    # HDMI receivers may retain power-on timings until explicitly synchronized.
    # Apply detected timings only on the selected source, before TRY_FMT.
    if candidate.get('detected_size') and candidate['signal'] == 'present':
        rc, _ = query(candidate['device'], '--set-dv-bt-timings=query')
        if rc:
            raise ValueError('Cannot apply detected HDMI timings to selected capture source')
    width, height = resolution.split('x')
    rc, out = query(candidate['device'], '--try-fmt-video=width='+width+',height='+height+',pixelformat='+fmt)
    size = re.search(r'Width/Height\s*:\s*(\d+)/(\d+)', out)
    pixel = re.search(r"Pixel Format\s*:\s*'([^']+)'", out)
    if rc or not size or not pixel or (size[1], size[2], pixel[1]) != (width, height, fmt):
        raise ValueError('Driver cannot accept requested capture resolution and format')


def discover():
    result = []
    aliases = sorted(Path('/dev/v4l/by-id').glob('*'))
    for entry in sorted(Path('/sys/class/video4linux').glob('video*')):
        dev = '/dev/' + entry.name
        rc, info = query(dev, '--all')
        if rc or not capture_caps(info):
            continue
        try:
            name = (entry / 'name').read_text().strip()
        except OSError:
            continue
        source = 'rk3588-synopsys-hdmirx' if name in ('snps_hdmirx', 'stream_hdmirx') else 'generic-v4l2'
        power_rc, power = query(dev, '--get-ctrl=power_present') if source == 'rk3588-synopsys-hdmirx' else (1, '')
        if power_rc == 0 and re.search(r'power_present:\s*(?:0x0+|0)\b', power):
            rc, timings = 1, ''
        else:
            rc, timings = query(dev, '--query-dv-timings')
        signal = 'present' if rc == 0 and re.search(r'Active width:\s*[1-9]', timings) else 'unknown'
        if source == 'rk3588-synopsys-hdmirx' and rc:
            signal = 'absent'
        _, fmts = query(dev, '--list-formats-ext')
        formats = re.findall(r"\[\d+\]:\s*'([^']+)'", fmts)
        stable = next((str(a) for a in aliases if a.resolve() == Path(dev)), dev)
        width = re.search(r'Active width:\s*(\d+)', timings)
        height = re.search(r'Active height:\s*(\d+)', timings)
        size = width[1]+'x'+height[1] if rc == 0 and width and height and int(width[1]) > 0 and int(height[1]) > 0 else None
        rate = re.search(r'\(([0-9.]+) frames per second\)', timings)
        fps = float(rate[1]) if rc == 0 and rate else None
        result.append(dict(device=stable, name=name, source=source, signal=signal, formats=formats, modes=parse_modes(fmts), detected_size=size, detected_fps=fps))
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--backend', required=True)
    p.add_argument('--device', default='')
    p.add_argument('--resolution', default='')
    p.add_argument('--framerate', default='')
    p.add_argument('--state', default='/run/vyos-kvm-over-ip/capture.json')
    a = p.parse_args()
    state = Path(a.state)
    try:
        old = json.loads(state.read_text()).get('device', '')
    except (OSError, ValueError):
        old = ''
    c = choose(discover(), a.device, old)
    c['format'] = select_format(compatible_formats(c, a.resolution, a.framerate), a.backend)
    validate_size(c, c['format'], a.resolution)
    c['requested_resolution'] = a.resolution
    c['requested_framerate'] = a.framerate
    c['backend'] = a.backend
    state.parent.mkdir(parents=True, exist_ok=True)
    temp = state.with_suffix('.tmp')
    temp.write_text(json.dumps(c, indent=2) + '\n')
    temp.replace(state)
    for key, value in [('DEVICE', c['device']), ('SOURCE_PROVIDER', c['source']), ('FOURCC', c['format'])]:
        print(key + '=' + shlex.quote(value))


if __name__ == '__main__':
    try:
        main()
    except ValueError as e:
        raise SystemExit(str(e))
