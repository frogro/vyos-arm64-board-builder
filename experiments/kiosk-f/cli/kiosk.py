"""Validated kiosk settings for the native VyOS container owner.

No service lifecycle, network changes, configuration writes or shell execution.
"""
import re
import os
import stat
from pathlib import Path
from urllib.parse import urlsplit

KEYS = {'url': 'KIOSK_URL', 'output': 'KIOSK_OUTPUT', 'rotation': 'KIOSK_ROTATION', 'graphics': 'KIOSK_GRAPHICS', 'video_decode': 'KIOSK_VIDEO_DECODE', 'video_h264_buffers': 'KIOSK_VIDEO_H264_BUFFERS', 'video_av1_buffers': 'KIOSK_VIDEO_AV1_BUFFERS'}


def environment(config):
    if 'kiosk' not in config:
        return []
    settings = config['kiosk']
    if not isinstance(settings, dict) or set(settings) - (set(KEYS) | {'remote'}):
        raise ValueError('Unknown kiosk setting')
    if any(key in config.get('environment', {}) for key in KEYS.values()):
        raise ValueError('Remove conflicting KIOSK_* environment overrides before using kiosk settings')
    url = settings.get('url')
    if not isinstance(url, str) or not url:
        raise ValueError('Kiosk URL is required')
    # Native Quadlet Environment is a quoted, line-based format. Refuse values
    # that could escape it. Percent literals must be escaped for systemd below.
    if any(ord(c) <= 32 or ord(c) == 127 or c in '\\"' for c in url):
        raise ValueError('URL must percent-encode whitespace, double quotes and backslashes')
    parsed = urlsplit(url)
    if not ((parsed.scheme in ('http', 'https') and parsed.hostname) or
            (parsed.scheme == 'file' and not parsed.netloc and parsed.path.startswith('/'))):
        raise ValueError('Kiosk URL must use http, https or an absolute local file URL')
    if parsed.username is not None or parsed.password is not None:
        raise ValueError('Do not store login credentials in the kiosk URL')
    # Validate malformed port syntax as well as the scheme.
    _ = parsed.port
    rotation = str(settings.get('rotation', '0'))
    if rotation not in ('0', '90', '180', '270'):
        raise ValueError('Kiosk rotation must be 0, 90, 180 or 270')
    output = settings.get('output', 'auto')
    if not isinstance(output, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]*', output):
        raise ValueError('Invalid kiosk output name')
    values = {'url': url, 'output': output, 'rotation': rotation}
    if 'graphics' in settings:
        if settings['graphics'] not in ('software', 'auto'):
            raise ValueError('Kiosk graphics must be software or auto')
        values['graphics'] = settings['graphics']
    for key, choices in {'video_decode': ('software', 'auto'),
                         'video_h264_buffers': ('disabled', 'enabled'),
                         'video_av1_buffers': ('disabled', 'enabled')}.items():
        if key in settings:
            if settings[key] not in choices:
                raise ValueError(f'Invalid kiosk {key}')
            values[key] = settings[key]
    if any(settings.get(key) == 'enabled' for key in ('video_h264_buffers', 'video_av1_buffers')) and settings.get('video_decode') != 'auto':
        raise ValueError('Capture buffer reserves require explicit video-decode auto')
    # Quadlet moves these into systemd ExecStart, where both specifiers (%)
    # and variable substitution ($) must remain literal URL characters.
    return [f'Environment={KEYS[key]}="{value.replace(chr(37), chr(37)*2).replace(chr(36), chr(36)*2)}"'
            for key, value in values.items()]


def resolve_input(source):
    node = Path(source).resolve(strict=True)
    info = node.stat()
    if not re.fullmatch(r'/dev/input/event[0-9]+', str(node)) or not stat.S_ISCHR(info.st_mode) or os.major(info.st_rdev) != 13:
        raise ValueError('Stable input source must resolve to an evdev character device')
    return str(node)


def devices(config, resolve=resolve_input):
    """Resolve selected kiosk inputs at generation; never modify saved config."""
    result, destinations = [], set()
    for item in config.get('device', {}).values():
        source, destination = item['source'], item['destination']
        if ('kiosk' in config and
                re.fullmatch(r'/dev/input/by-(?:id|path)/[^/\s:%]+', source) and
                re.fullmatch(r'/dev/input/event[0-9]+', destination)):
            try:
                destination = resolve(source)
            except (OSError, ValueError) as error:
                raise ValueError(f'Cannot resolve selected kiosk input {source}: {error}') from error
        if 'kiosk' in config and destination in destinations:
            raise ValueError(f'Conflicting kiosk device destination: {destination}')
        destinations.add(destination)
        result.append((source, destination))
    return result
