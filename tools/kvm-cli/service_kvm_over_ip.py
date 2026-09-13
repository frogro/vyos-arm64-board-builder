#!/usr/bin/env python3

import ipaddress
import json
import os
import re
import shlex
import subprocess
from pathlib import Path
from sys import exit

from vyos.config import Config
from vyos.configdict import is_node_changed
from vyos import ConfigError
from vyos import airbag

airbag.enable()

BASE = ['service', 'kvm-over-ip']

RUN_DIR = Path('/run/vyos-kvm-over-ip')
VIDEO_ENV = RUN_DIR / 'video.env'
MEDIAMTX_CONFIG = RUN_DIR / 'mediamtx.yml'

PROFILE_DIR = Path('/usr/share/vyos-arm64-board-builder')
PROFILE_JSON = PROFILE_DIR / 'profile.json'
GADGET_PROVIDER_ENV = PROFILE_DIR / 'kvm-gadget-provider.env'

GADGET = '/usr/local/sbin/vyos-kvm-gadget'
VIDEO_SERVICE = 'vyos-kvm-video.service'
MEDIAMTX_SERVICE = 'vyos-kvm-mediamtx.service'
MEDIA_ROOT = Path('/config/kvm-over-ip/media')


def _as_int(value, name, minimum, maximum):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ConfigError(f'{name} must be an integer')
    if number < minimum or number > maximum:
        raise ConfigError(f'{name} must be between {minimum} and {maximum}')
    return number


def _profile():
    try:
        return json.loads(PROFILE_JSON.read_text())
    except Exception:
        return {}


def _provider():
    return _profile().get('kvm', {}).get('hardware_provider', 'generic-v4l2')


def _parse_provider_env():
    result = {}
    if not GADGET_PROVIDER_ENV.is_file():
        return result

    for raw in GADGET_PROVIDER_ENV.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        result[key.strip()] = value
    return result


def _gadget_port(kvm):
    configured = kvm.get('usb', {}).get('port')
    provider = _parse_provider_env()
    return configured or provider.get('KVM_GADGET_DEFAULT_PORT')


def _gadget_features(kvm):
    mouse = kvm.get('mouse', {})
    virtual_media = kvm.get('virtual_media', {})
    return {
        'keyboard': 'keyboard' in kvm,
        'mouse_absolute': 'absolute' in mouse,
        'mouse_relative': 'relative' in mouse,
        'virtual_media': virtual_media.get('file'),
    }


def get_config(config=None):
    conf = config if config else Config()

    if not conf.exists(BASE):
        return None

    kvm = conf.get_config_dict(
        BASE,
        key_mangling=('-', '_'),
        get_first_key=True,
    )

    kvm['_video_changed'] = is_node_changed(conf, BASE + ['video'])
    kvm['_gadget_changed'] = any(
        is_node_changed(conf, BASE + suffix)
        for suffix in (
            ['keyboard'],
            ['mouse'],
            ['usb'],
            ['virtual-media'],
        )
    )

    if 'video' in kvm:
        video = kvm['video']
        video.setdefault('listen_address', '0.0.0.0')
        video.setdefault('port', '8889')

        backend = video.get('backend')
        if backend in ('ffmpeg', 'gstreamer'):
            video.setdefault('bitrate', '8000')
            video.setdefault('gop', '60')

    return kvm


def verify(kvm):
    if not kvm:
        return None

    video = kvm.get('video')
    mouse = kvm.get('mouse', {})
    virtual_media = kvm.get('virtual_media', {})

    gadget_requested = (
        'keyboard' in kvm
        or 'absolute' in mouse
        or 'relative' in mouse
        or 'file' in virtual_media
    )

    if not video and not gadget_requested:
        raise ConfigError(
            'KVM-over-IP must configure video, keyboard, mouse or virtual-media'
        )

    if 'usb' in kvm and not gadget_requested:
        raise ConfigError(
            'USB gadget port is only meaningful with keyboard, mouse or virtual-media'
        )

    if video:
        backend = video.get('backend')
        if backend not in ('ustreamer', 'gstreamer', 'ffmpeg'):
            raise ConfigError(
                'Video backend must be one of: ustreamer, gstreamer, ffmpeg'
            )

        if backend == 'ustreamer':
            if 'bitrate' in video:
                raise ConfigError('Video bitrate is not valid with ustreamer')
            if 'gop' in video:
                raise ConfigError('Video GOP is not valid with ustreamer')

        if backend in ('ffmpeg', 'gstreamer'):
            _as_int(video.get('bitrate', 8000), 'Video bitrate', 250, 100000)
            _as_int(video.get('gop', 60), 'Video GOP', 1, 600)

        if 'framerate' in video:
            _as_int(video['framerate'], 'Video framerate', 1, 240)

        if 'port' in video:
            _as_int(video['port'], 'Video port', 1, 65535)

        if 'resolution' in video:
            match = re.fullmatch(
                r'([0-9]{2,5})x([0-9]{2,5})',
                str(video['resolution']),
            )
            if not match:
                raise ConfigError(
                    'Video resolution must use WIDTHxHEIGHT, for example 1920x1080'
                )
            width, height = int(match.group(1)), int(match.group(2))
            if width < 64 or height < 64 or width > 8192 or height > 8192:
                raise ConfigError('Video resolution is outside the supported CLI range')

        if 'device' in video:
            if not re.fullmatch(r'/dev/video[0-9]+', str(video['device'])):
                raise ConfigError('Video device must be /dev/videoN')

        try:
            listen = ipaddress.ip_address(
                str(video.get('listen_address', '0.0.0.0'))
            )
        except ValueError:
            raise ConfigError('Video listen-address must be a valid IPv4 address')

        if listen.version != 4:
            raise ConfigError('Video listen-address currently supports IPv4 only')

    if gadget_requested:
        if not os.path.isfile(GADGET):
            raise ConfigError(f'KVM gadget runtime is missing: {GADGET}')

        provider_env = _parse_provider_env()
        if not provider_env:
            raise ConfigError(
                'This image has no KVM USB-gadget provider runtime metadata'
            )

        ports = provider_env.get('KVM_GADGET_PORTS', '').split()
        selected_port = _gadget_port(kvm)

        if not selected_port:
            raise ConfigError('KVM provider does not define a default USB gadget port')

        if ports and selected_port not in ports:
            raise ConfigError(
                f"USB gadget port '{selected_port}' is not provided by this board "
                f"(available: {', '.join(ports)})"
            )

    if 'file' in virtual_media:
        requested = Path(str(virtual_media['file']))
        try:
            root = MEDIA_ROOT.resolve(strict=True)
            resolved = requested.resolve(strict=True)
        except FileNotFoundError:
            raise ConfigError(f'Virtual-media ISO does not exist: {requested}')

        if not resolved.is_file() or resolved.stat().st_size == 0:
            raise ConfigError('Virtual-media file must be a non-empty regular file')

        try:
            resolved.relative_to(root)
        except ValueError:
            raise ConfigError(f'Virtual-media ISO must be below {MEDIA_ROOT}')

        if resolved.suffix.lower() != '.iso':
            raise ConfigError(
                'Virtual-media currently supports read-only .iso files only'
            )

    return None


def _write_env(values):
    RUN_DIR.mkdir(mode=0o755, parents=True, exist_ok=True)
    VIDEO_ENV.write_text(
        '\n'.join(f'{key}={shlex.quote(str(value))}' for key, value in values.items())
        + '\n'
    )
    os.chmod(VIDEO_ENV, 0o600)


def generate(kvm):
    RUN_DIR.mkdir(mode=0o755, parents=True, exist_ok=True)

    if not kvm or 'video' not in kvm:
        VIDEO_ENV.unlink(missing_ok=True)
        MEDIAMTX_CONFIG.unlink(missing_ok=True)
        return None

    video = kvm['video']
    backend = video['backend']

    _write_env({
        'KVM_VIDEO_BACKEND': backend,
        'KVM_VIDEO_PROVIDER': _provider(),
        'KVM_VIDEO_DEVICE': video.get('device', ''),
        'KVM_VIDEO_RESOLUTION': video.get('resolution', ''),
        'KVM_VIDEO_FRAMERATE': video.get('framerate', ''),
        'KVM_VIDEO_BITRATE': video.get('bitrate', '8000'),
        'KVM_VIDEO_GOP': video.get('gop', '60'),
        'KVM_VIDEO_LISTEN_ADDRESS': video.get('listen_address', '0.0.0.0'),
        'KVM_VIDEO_PORT': video.get('port', '8889'),
        # Policy: uStreamer quality is fixed, not exposed in the CLI.
        'KVM_VIDEO_USTREAMER_QUALITY': '80',
    })

    if backend in ('ffmpeg', 'gstreamer'):
        listen = video.get('listen_address', '0.0.0.0')
        port = video.get('port', '8889')
        MEDIAMTX_CONFIG.write_text(
            'logLevel: info\n'
            'rtsp: true\n'
            'rtspAddress: 127.0.0.1:8554\n'
            'rtspTransports: [tcp]\n'
            'rtmp: false\n'
            'hls: false\n'
            'srt: false\n'
            'api: false\n'
            'metrics: false\n'
            'playback: false\n'
            'webrtc: true\n'
            f'webrtcAddress: {listen}:{port}\n'
            'webrtcAllowOrigins: ["*"]\n'
            'paths:\n'
            '  kvm:\n'
            '    source: publisher\n'
        )
        os.chmod(MEDIAMTX_CONFIG, 0o600)
    else:
        MEDIAMTX_CONFIG.unlink(missing_ok=True)

    return None


def _systemctl(*args, check=False):
    return subprocess.run(
        ['systemctl', *args],
        check=check,
        text=True,
    ).returncode


def _run_gadget(args, port=None, check=True):
    env = os.environ.copy()
    if port:
        env['KVM_GADGET_PORT'] = port

    return subprocess.run(
        [GADGET, *args],
        env=env,
        check=check,
        text=True,
    ).returncode


def _apply_gadget(kvm):
    # Reconcile from VyOS configuration. Gadget-only commits may reconnect
    # USB; video-only commits do not touch the gadget.
    _run_gadget(['destroy'], check=False)

    if not kvm:
        return

    features = _gadget_features(kvm)
    if not any(bool(value) for value in features.values()):
        return

    port = _gadget_port(kvm)

    if features['keyboard']:
        _run_gadget(['keyboard', 'enable'], port=port)

    if features['mouse_absolute']:
        _run_gadget(['mouse', 'absolute', 'enable'], port=port)

    if features['mouse_relative']:
        _run_gadget(['mouse', 'relative', 'enable'], port=port)

    if features['virtual_media']:
        _run_gadget(
            ['virtual-media', 'attach', str(features['virtual_media'])],
            port=port,
        )

    _run_gadget(['bind'], port=port)


def apply(kvm):
    if not kvm:
        _systemctl('stop', VIDEO_SERVICE)
        _systemctl('stop', MEDIAMTX_SERVICE)
        _apply_gadget(None)
        return None

    if kvm.get('_video_changed', True):
        video = kvm.get('video')

        if not video:
            _systemctl('stop', VIDEO_SERVICE)
            _systemctl('stop', MEDIAMTX_SERVICE)
        else:
            backend = video['backend']

            if backend in ('ffmpeg', 'gstreamer'):
                _systemctl('restart', MEDIAMTX_SERVICE, check=True)
            else:
                _systemctl('stop', MEDIAMTX_SERVICE)

            _systemctl('restart', VIDEO_SERVICE, check=True)

    if kvm.get('_gadget_changed', True):
        _apply_gadget(kvm)

    return None


if __name__ == '__main__':
    try:
        config = get_config()
        verify(config)
        generate(config)
        apply(config)
    except ConfigError as e:
        print(e)
        exit(1)
    except subprocess.CalledProcessError as e:
        print(f'KVM-over-IP runtime command failed: {e}')
        exit(1)
