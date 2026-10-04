#!/usr/bin/env python3
"""Read-only decoder capability discovery; never claims a verified network stream."""
import fcntl
import json
import os
from pathlib import Path
import struct
import sys


def memory():
    try:
        return {line.split(':')[0]: int(line.split()[1]) for line in
                Path('/proc/meminfo').read_text().splitlines() if line.startswith(('CmaTotal:', 'CmaFree:'))}
    except (OSError, ValueError):
        return {}


def h264_devices():
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst
    Gst.init(None)
    rows = []
    for factory in Gst.Registry.get().get_feature_list(Gst.ElementFactory):
        name = factory.get_name()
        if not (name.startswith('v4l2sl') and name.endswith('h264dec')):
            continue
        element = factory.create(None)
        device = element.get_property('video-device')
        row = {'factory': name, 'device': device, 'sizes': []}
        try:
            fd = os.open(device, os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC)
            try:
                for index in range(64):
                    data = bytearray(44)
                    struct.pack_into('II', data, 0, index, int.from_bytes(b'S264', 'little'))
                    try:
                        fcntl.ioctl(fd, 0xc02c564a, data, True)  # VIDIOC_ENUM_FRAMESIZES
                    except OSError:
                        break
                    kind = struct.unpack_from('I', data, 8)[0]
                    if kind == 1:
                        w, h = struct.unpack_from('II', data, 12)
                        row['sizes'].append([w, w, 1, h, h, 1])
                    elif kind in (2, 3):
                        row['sizes'].append(list(struct.unpack_from('6I', data, 12)))
            finally:
                os.close(fd)
        except OSError as error:
            row['error'] = str(error)
        rows.append(row)
    return rows


def fits(size, width, height):
    low_w, high_w, step_w, low_h, high_h, step_h = size
    if step_w < 1 or step_h < 1:
        return False
    coded_w = low_w + max(0, (width-low_w+step_w-1)//step_w)*step_w
    coded_h = low_h + max(0, (height-low_h+step_h-1)//step_h)*step_h
    return low_w <= coded_w <= high_w and low_h <= coded_h <= high_h


def select(rows, resolution):
    width, height = map(int, resolution.split('x'))
    eligible = [row for row in rows if any(fits(size, width, height) for size in row['sizes'])]
    # Prefer the broadest eligible device, including when the sender exceeds its
    # requested size. Node indices and driver names are not a board ABI.
    eligible.sort(key=lambda row: max(size[1]*size[4] for size in row['sizes']), reverse=True)
    chosen = eligible[0]['factory'] if eligible else None
    ranks = {row['factory']: 0 for row in rows if row['sizes'] and row not in eligible}
    if chosen:
        ranks[chosen] = 300
    return {'selected': chosen, 'ranks': ranks, 'devices': rows, 'resolution': resolution}


def status():
    import base64
    cfg = json.loads(base64.b64decode(os.environ.get('G_RECEIVER_CONFIG', 'e30=')))
    result = {'requested': cfg, 'actual_decoder': 'unknown: requires stream evidence',
              'hardware_confirmed': False, 'cma_kib': memory(),
              'visible_devices': sorted(str(p) for pattern in ('/dev/video*', '/dev/media*', '/dev/dma_heap/*', '/dev/dri/*') for p in Path('/').glob(pattern.lstrip('/')) if p.is_char_device())}
    try:
        result['h264_selection'] = select(h264_devices(), cfg.get('resolution', '1920x1080'))
    except (ImportError, OSError, ValueError) as error:
        result['probe_error'] = str(error)
    for path, key in [('/state/receiver-selection.json', 'startup_selection'), ('/state/steamlink-runtime.json', 'steamlink_startup'), ('/state/receiver-stream.json', 'last_stream')]:
        try:
            result[key] = json.loads(Path(path).read_text())
        except (OSError, ValueError):
            pass
    stream = result.get('last_stream', {})
    if stream.get('active') and isinstance(stream.get('pid'), int):
        try:
            active = b'miracle-player.py' in Path(f"/proc/{stream['pid']}/cmdline").read_bytes()
        except OSError:
            active = False
        stream['active'] = active
        if active:
            result['actual_decoder'] = stream.get('actual_decoder', 'unknown')
            result['hardware_confirmed'] = bool(stream.get('hardware_confirmed'))
    result['limitations'] = ['Capabilities and startup selection are not proof of the active stream decoder.',
                            'Steam Link remains limited to H264/HEVC at 1080p60.',
                            'Miracast resolution/fps are negotiated with the sender, not set by the generic CLI fields.']
    return result


if __name__ == '__main__':
    print(json.dumps(select(h264_devices(), sys.argv[2]) if sys.argv[1:2] == ['select'] else status(), indent=2))
