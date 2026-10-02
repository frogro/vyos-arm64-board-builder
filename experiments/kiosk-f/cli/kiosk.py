"""Validated kiosk settings for the native VyOS container owner.

No service lifecycle, network changes, configuration writes or shell execution.
"""
import re
import os
import stat
import fcntl
import struct
from pathlib import Path
from urllib.parse import urlsplit

KEYS = {'display_backend': 'KIOSK_DISPLAY_BACKEND', 'url': 'KIOSK_URL', 'output': 'KIOSK_OUTPUT', 'rotation': 'KIOSK_ROTATION', 'graphics': 'KIOSK_GRAPHICS', 'video_decode': 'KIOSK_VIDEO_DECODE', 'video_h264_buffers': 'KIOSK_VIDEO_H264_BUFFERS', 'video_av1_buffers': 'KIOSK_VIDEO_AV1_BUFFERS'}


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
    if 'display_backend' in settings:
        if settings['display_backend'] not in ('x11', 'wayland'):
            raise ValueError('Kiosk display backend must be x11 or wayland')
        values['display_backend'] = settings['display_backend']
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
    if any(settings.get(key) == 'enabled' for key in ('video_h264_buffers', 'video_av1_buffers')) and settings.get('video_decode') not in ('auto', 'software'):
        raise ValueError('Capture buffer reserves require explicit video-decode auto or software')
    # Quadlet moves these into systemd ExecStart, where both specifiers (%)
    # and variable substitution ($) must remain literal URL characters.
    result = [f'Environment={KEYS[key]}="{value.replace(chr(37), chr(37)*2).replace(chr(36), chr(36)*2)}"'
              for key, value in values.items()]
    remote = settings.get('remote', {})
    if settings.get('display_backend') == 'wayland' and remote.get('access') == 'enabled':
        result.append('Environment=SUNSHINE_VYARM_DIRECT_RGA="1"')
        volumes = config.get('volume', {}).values()
        matching = [v for v in volumes if v.get('destination') == '/run/mpp/compatible']
        if matching and any(v.get('source') != '/sys/firmware/devicetree/base/compatible' for v in matching):
            raise ValueError('Conflicting MPP compatible volume')
        if not matching:
            result.append('Volume=/sys/firmware/devicetree/base/compatible:/run/mpp/compatible:ro')
    if (settings.get('display_backend') == 'wayland'
            and remote.get('access') == 'enabled' and remote.get('input') == 'control'):
        # Host companion creates only Sunshine-owned nodes; target gains no mknod.
        result.append('PodmanArgs=--device-cgroup-rule="c 13:* rw"')
    for item in config.get('device', {}).values():
        if optional_input(config, item):
            result.append(f"# KioskInput={item['source']}:{item['destination']}")
    return result


def optional_input(config, item):
    """Only explicitly selected stable kiosk evdev inputs may be absent."""
    return ('kiosk' in config and
            bool(re.fullmatch(r'/dev/input/by-(?:id|path)/[^/\s:%]+', item.get('source', ''))) and
            bool(re.fullmatch(r'/dev/input/event[0-9]+', item.get('destination', ''))))


def resolve_input(source):
    node = Path(source).resolve(strict=True)
    info = node.stat()
    if not re.fullmatch(r'/dev/input/event[0-9]+', str(node)) or not stat.S_ISCHR(info.st_mode) or os.major(info.st_rdev) != 13:
        raise ValueError('Stable input source must resolve to an evdev character device')
    return str(node)


def request_decoder(path):
    """Query capabilities/formats only; never allocate buffers or start streaming."""
    fd = os.open(path, os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        cap = bytearray(104)
        fcntl.ioctl(fd, 0x80685600, cap, True)
        flags = struct.unpack_from('I', cap, 84)[0]
        if flags & 0x80000000:
            flags = struct.unpack_from('I', cap, 88)[0]
        if not flags & (0x4000 | 0x8000):
            return False
        for queue in (2, 10):
            for index in range(64):
                fmt = bytearray(64)
                struct.pack_into('II', fmt, 0, index, queue)
                try:
                    fcntl.ioctl(fd, 0xc0405602, fmt, True)
                except OSError:
                    break
                if bytes(fmt[44:48]) in (b'S264', b'S265', b'VP9F', b'AV1F'):
                    return True
        return False
    finally:
        os.close(fd)


def decoder_devices(sysroot=Path('/sys/class/video4linux'), devroot=Path('/dev'),
                    probe=request_decoder):
    """Select request decoders and their own media controller, regardless of number."""
    result = set()
    for entry in sorted(sysroot.glob('video*')):
        if not re.fullmatch(r'video[0-9]+', entry.name):
            continue
        video = devroot / entry.name
        try:
            if not stat.S_ISCHR(video.stat().st_mode) or not probe(str(video)):
                continue
            media = [devroot / p.name for p in (entry / 'device').glob('media*')
                     if re.fullmatch(r'media[0-9]+', p.name)]
            media = [p for p in media if stat.S_ISCHR(p.stat().st_mode)]
            if media:
                result.add(str(video))
                result.update(map(str, media))
        except OSError:
            continue  # Absent/busy/inaccessible hardware: browser can fall back.
    return [(p, p) for p in sorted(result)]


def devices(config, resolve=resolve_input, discover=decoder_devices):
    """Resolve selected kiosk inputs at generation; never modify saved config."""
    result, destinations = [], set()
    for item in config.get('device', {}).values():
        source, destination = item['source'], item['destination']
        if ('kiosk' in config and
                re.fullmatch(r'/dev/input/by-(?:id|path)/[^/\s:%]+', source) and
                re.fullmatch(r'/dev/input/event[0-9]+', destination)):
            try:
                destination = resolve(source)
            except FileNotFoundError:
                continue  # Selected device stays recorded in KioskInput metadata.
            except (OSError, ValueError) as error:
                raise ValueError(f'Cannot resolve selected kiosk input {source}: {error}') from error
        if 'kiosk' in config and destination in destinations:
            raise ValueError(f'Conflicting kiosk device destination: {destination}')
        destinations.add(destination)
        result.append((source, destination))
    settings = config.get('kiosk', {})
    if settings.get('display_backend') == 'wayland' and settings.get('remote', {}).get('access') == 'enabled':
        required = ['/dev/mpp_service', '/dev/dma_heap/system']
        required += [str(p) for p in Path('/dev/dri').glob('renderD*')]
        rga = [str(Path('/dev') / p.parent.name) for p in Path('/sys/class/video4linux').glob('video*/name')
               if p.read_text().strip() == 'rockchip-rga']
        if len(rga) != 1 or len(required) != 3:
            raise ValueError('Wayland remote requires one supported RGA and render device')
        required += rga
        if settings['remote'].get('input') == 'control':
            required.append('/dev/uinput')
        for node in required:
            if not Path(node).is_char_device():
                raise ValueError(f'Wayland remote device unavailable: {node}')
            if (node, node) not in result:
                if node in destinations:
                    raise ValueError(f'Conflicting remote device destination: {node}')
                result.append((node, node)); destinations.add(node)
    if config.get('kiosk', {}).get('video_decode') == 'auto':
        for source, destination in discover():
            if (source, destination) in result:
                continue
            if destination in destinations:
                raise ValueError(f'Conflicting kiosk decoder destination: {destination}')
            result.append((source, destination))
            destinations.add(destination)
    return result
