"""Validated kiosk settings for the native VyOS container owner.

No service lifecycle, network changes, configuration writes or shell execution.
"""
import re
import errno
import json
import os
import stat
import fcntl
import struct
from pathlib import Path
from urllib.parse import urlsplit

KEYS = {'audio_muted': 'KIOSK_AUDIO_MUTED', 'display_backend': 'KIOSK_DISPLAY_BACKEND', 'url': 'KIOSK_URL', 'output': 'KIOSK_OUTPUT', 'rotation': 'KIOSK_ROTATION', 'graphics': 'KIOSK_GRAPHICS', 'video_decode': 'KIOSK_VIDEO_DECODE', 'video_h264_buffers': 'KIOSK_VIDEO_H264_BUFFERS', 'video_av1_buffers': 'KIOSK_VIDEO_AV1_BUFFERS'}


RUNTIME = Path('/usr/share/vyos-arm64-board-builder/kiosk-runtime/runtime.json')
BUILDER_IMAGE = re.compile(r'localhost/vyarm-kiosk:github-[0-9]+')


def runtime_images(containers, manifest=RUNTIME):
    """Resolve builder-managed images against the booted ISO, without config writes.

    Only generated github-run tags participate. Custom images remain pinned.
    Both candidate and effective dictionaries must be resolved before comparison.
    """
    managed = [item for item in containers.get('name', {}).values()
               if 'kiosk' in item and BUILDER_IMAGE.fullmatch(item.get('image', ''))]
    if not managed:
        return
    try:
        meta = json.loads(Path(manifest).read_text())
        image = meta['image']
        image_id = meta['image_id'].removeprefix('sha256:')
        if not BUILDER_IMAGE.fullmatch(image) or not re.fullmatch(r'[0-9a-f]{64}', image_id):
            raise ValueError('Invalid bundled kiosk runtime identity')
    except (OSError, KeyError, TypeError, AttributeError, ValueError) as error:
        raise ValueError(f'Cannot select the bundled kiosk runtime: {error}') from error
    for item in managed:
        item['image'] = image


def environment(config):
    if 'kiosk' not in config:
        return []
    settings = config['kiosk']
    if not isinstance(settings, dict) or set(settings) - (set(KEYS) | {'remote', 'display_schedule'}):
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
    if 'audio_muted' in settings and settings.get('display_backend') != 'wayland':
        raise ValueError('Audio mute currently requires the Wayland supervisor')
    values = {'url': url, 'output': output, 'rotation': rotation}
    if 'display_backend' in settings:
        if settings['display_backend'] not in ('x11', 'wayland'):
            raise ValueError('Kiosk display backend must be x11 or wayland')
        values['display_backend'] = settings['display_backend']
    if 'graphics' in settings:
        if settings['graphics'] not in ('software', 'auto'):
            raise ValueError('Kiosk graphics must be software or auto')
        values['graphics'] = settings['graphics']
    for key, choices in {'audio_muted': ('enabled', 'disabled'), 'video_decode': ('software', 'auto'),
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
    if 'display_schedule' in settings:
        if settings.get('display_backend') != 'wayland':
            raise ValueError('Display schedule currently requires the Wayland supervisor')
        from vyos.kiosk_schedule import validate
        schedule = validate(settings['display_schedule'])
        for key, value in schedule.items():
            env_key = 'KIOSK_DISPLAY_' + key.upper()
            if env_key in config.get('environment', {}):
                raise ValueError('Remove conflicting display schedule environment override')
            result.append(f'Environment={env_key}="{value}"')
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


def h264_limit(path):
    """Query advertised H.264 slice dimensions without configuring the device."""
    fd = os.open(path, os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        best = (0, 0)
        for index in range(64):
            size = bytearray(44)  # struct v4l2_frmsizeenum
            struct.pack_into('I4s', size, 0, index, b'S264')
            try:
                fcntl.ioctl(fd, 0xc02c564a, size, True)  # VIDIOC_ENUM_FRAMESIZES
            except OSError as error:
                if error.errno == errno.EINVAL:  # EINVAL: no further sizes / unsupported format
                    break
                raise
            kind = struct.unpack_from('I', size, 8)[0]
            if kind == 1:  # discrete
                width, height = struct.unpack_from('II', size, 12)
            elif kind in (2, 3):  # continuous / stepwise
                width = struct.unpack_from('I', size, 16)[0]
                height = struct.unpack_from('I', size, 28)[0]
            else:
                continue
            best = max(best, (width, height), key=lambda v: (v[0] * v[1], v))
        return best
    finally:
        os.close(fd)


def prioritize_h264(bindings, discovered, probe=h264_limit):
    """Give Chromium the most capable H.264 node first, inside this container.

    Chromium scans video numbers and picks the first codec match, without
    considering stream size. Exchange only canonical decoder destinations;
    keep all devices, media controllers, capture nodes and explicit aliases.
    """
    nodes = {src for src, dst in discovered
             if src == dst and re.fullmatch(r'/dev/video[0-9]+', src)}
    candidates = [(src, dst) for src, dst in bindings if src == dst and src in nodes]
    if len(candidates) < 2:
        return bindings
    try:
        limits = {src: probe(src) for src, _ in candidates}
    except OSError:
        return bindings  # Unknown capabilities: do not guess or remove grants.
    nodes = [src for src, _ in candidates if all(limits[src])]
    if len(nodes) < 2 or len({limits[src] for src in nodes}) == 1:
        return bindings
    destinations = sorted(nodes, key=lambda p: int(p.removeprefix('/dev/video')))
    sources = sorted(nodes, key=lambda p: (-limits[p][0] * limits[p][1],
                                         int(p.removeprefix('/dev/video'))))
    mapping = dict(zip(sources, destinations))
    return [(src, mapping.get(src, dst) if src == dst else dst) for src, dst in bindings]


def devices(config, resolve=resolve_input, discover=decoder_devices, rank=prioritize_h264):
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
        discovered = discover()
        for source, destination in discovered:
            if (source, destination) in result:
                continue
            if destination in destinations:
                raise ValueError(f'Conflicting kiosk decoder destination: {destination}')
            result.append((source, destination))
            destinations.add(destination)
        result = rank(result, discovered)
    return result
