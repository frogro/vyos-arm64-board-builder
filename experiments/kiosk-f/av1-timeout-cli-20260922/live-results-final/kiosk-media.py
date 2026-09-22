#!/usr/bin/env python3
"""Browser playback policy. Availability is not proof of per-stream hardware use."""
import hashlib
import fcntl
import struct
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

MANIFEST = Path('/usr/share/vyarm/kiosk-media-capabilities.json')
STATUS = Path('/run/kiosk/media-status.json')
FEATURES = {'h264': 'V4L2ExtraCaptureBuffers', 'av1': 'V4L2ExtraAV1CaptureBuffers'}


def plan(env, capabilities, devices):
    mode = env.get('KIOSK_VIDEO_DECODE')
    reserves = {c: env.get('KIOSK_VIDEO_' + c.upper() + '_BUFFERS') for c in FEATURES}
    if mode not in (None, 'auto', 'software'):
        raise ValueError('video-decode must be auto or software')
    if any(v not in (None, 'disabled', 'enabled') for v in reserves.values()):
        raise ValueError('Capture buffer reserve must be disabled or enabled')
    if any(v == 'enabled' for v in reserves.values()) and mode != 'auto':
        raise ValueError('Capture buffer reserves require explicit video-decode auto')
    status = {'requested': mode or 'legacy', 'actual_decoder': 'unknown: requires per-video browser evidence',
              'hardware_confirmed': False, 'devices': devices, 'active_features': [],
              'fallback_reason': None, 'software_fallback': 'codec/profile dependent; HEVC may be unsupported'}
    args = []
    if mode is None:
        return args, status
    if mode == 'software':
        return ['--disable-accelerated-video-decode'], status
    backend = capabilities.get('backend')
    if backend != 'v4l2-request' or not capabilities.get('verified_binary'):
        status['fallback_reason'] = 'No verified hardware browser/runtime recipe; keep browser automatic selection'
        return args, status
    if capabilities.get('graphics_backend') == 'wayland' and not env.get('WAYLAND_DISPLAY'):
        status['fallback_reason'] = 'Validated recipe requires Wayland; keep browser automatic selection'
        return args, status
    if not devices.get('decoder') or not devices.get('media') or not devices.get('render'):
        status['fallback_reason'] = 'Decoder/media/render access missing; keep browser automatic selection'
        return args, status
    # Only the tested runtime recipe may select a backend. Never infer it from a board name.
    args += capabilities.get('arguments', [])
    status['active_features'] += capabilities.get('base_features', [])
    for codec, value in reserves.items():
        if value == 'enabled':
            feature = FEATURES[codec]
            if feature not in capabilities.get('features', []):
                raise ValueError('Browser does not support ' + feature)
            status['active_features'].append(feature)
    return args, status


def probe():
    result = {'decoder': [], 'media': [], 'render': []}
    for pattern, kind in (('/dev/video*', 'decoder'), ('/dev/media*', 'media'), ('/dev/dri/renderD*', 'render')):
        import glob
        for path in sorted(glob.glob(pattern)):
            try:
                if not stat.S_ISCHR(os.stat(path).st_mode) or not os.access(path, os.R_OK | os.W_OK):
                    continue
                if kind == 'decoder':
                    fd = os.open(path, os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC)
                    try:
                        cap = bytearray(104)
                        fcntl.ioctl(fd, 0x80685600, cap, True)  # VIDIOC_QUERYCAP
                        flags = struct.unpack_from('I', cap, 84)[0]
                        if flags & 0x80000000:
                            flags = struct.unpack_from('I', cap, 88)[0]
                        if not flags & (0x4000 | 0x8000):  # M2M / M2M_MPLANE
                            continue
                        formats = []
                        for queue in (2, 10):  # OUTPUT, OUTPUT_MPLANE
                            for index in range(64):
                                fmt = bytearray(64)
                                struct.pack_into('II', fmt, 0, index, queue)
                                try:
                                    fcntl.ioctl(fd, 0xc0405602, fmt, True)  # VIDIOC_ENUM_FMT
                                except OSError:
                                    break
                                formats.append(bytes(fmt[44:48]).decode('ascii', errors='replace'))
                        if not set(formats) & {'S264', 'S265', 'VP9F', 'AV1F'}:
                            continue
                    finally:
                        os.close(fd)
                result[kind].append(path)
            except (OSError, subprocess.SubprocessError):
                continue
    return result


def capabilities():
    try:
        data = json.loads(MANIFEST.read_text())
        if data.get('version') != 1:
            return {}
        binary = Path(data['binary'])
        # Root-owned image manifest selects the executable, never saved user configuration.
        if not binary.is_absolute():
            return {}
        with binary.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        data['verified_binary'] = digest == data['sha256']
        if not isinstance(data.get('arguments', []), list) or not all(isinstance(a, str) and a.startswith('--') and not a.startswith(('--enable-features=', '--disable-features=')) for a in data.get('arguments', [])):
            return {}
        return data
    except (OSError, ValueError, KeyError):
        return {}


def browser_policy(env):
    caps = capabilities() if env.get('KIOSK_VIDEO_DECODE') in ('auto', 'software') else {}
    devices = probe() if env.get('KIOSK_VIDEO_DECODE') == 'auto' else {}
    args, status = plan(env, caps, devices)
    status['executable'] = caps['binary'] if caps.get('verified_binary') else 'chromium'
    status['runtime_version'] = caps.get('version')
    status['browser_sha256'] = caps.get('sha256') if caps.get('verified_binary') else None
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATUS.with_suffix('.tmp')
    tmp.write_text(json.dumps(status, indent=2) + '\n')
    tmp.replace(STATUS)
    return args, status


if __name__ == '__main__':
    if sys.argv[1:] == ['status']:
        try:
            print(STATUS.read_text())
        except FileNotFoundError:
            print(json.dumps({'actual_decoder': 'unknown', 'reason': 'No media policy startup report'}))
    else:
        args, status = browser_policy(os.environ)
        print(json.dumps({'arguments': args, 'status': status}))
