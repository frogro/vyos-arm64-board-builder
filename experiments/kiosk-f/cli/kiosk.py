"""Validated kiosk settings for the native VyOS container owner.

No service lifecycle, network changes, configuration writes or shell execution.
"""
import re
from urllib.parse import urlsplit

KEYS = {'url': 'KIOSK_URL', 'output': 'KIOSK_OUTPUT', 'rotation': 'KIOSK_ROTATION'}


def environment(config):
    if 'kiosk' not in config:
        return []
    settings = config['kiosk']
    if not isinstance(settings, dict) or set(settings) - (set(KEYS) | {'remote'}):
        raise ValueError('Unknown kiosk setting')
    if any(key in config.get('environment', {}) for key in KEYS.values()):
        raise ValueError('Remove KIOSK_URL/KIOSK_OUTPUT/KIOSK_ROTATION environment overrides before using kiosk settings')
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
    # Quadlet moves these into systemd ExecStart, where both specifiers (%)
    # and variable substitution ($) must remain literal URL characters.
    return [f'Environment={KEYS[key]}="{value.replace(chr(37), chr(37)*2).replace(chr(36), chr(36)*2)}"'
            for key, value in values.items()]
