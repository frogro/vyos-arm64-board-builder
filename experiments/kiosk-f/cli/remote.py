"""Sunshine policy generation for the native container owner (no board assumptions)."""
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path('/run/vyos-kiosk')
DEST = '/run/vyos-kiosk-policy'

def policy(config):
    remote = config.get('kiosk', {}).get('remote', {})
    if not isinstance(remote, dict) or set(remote) - {'access', 'input', 'audio'}:
        raise ValueError('Unknown kiosk remote setting')
    result = {'version': 1, 'access': remote.get('access', 'disabled'),
              'input': remote.get('input', 'view-only'), 'audio': remote.get('audio', 'disabled')}
    for key, choices in {'access': ('enabled', 'disabled'), 'input': ('view-only', 'control'),
                         'audio': ('enabled', 'disabled')}.items():
        if result[key] not in choices:
            raise ValueError(f'Invalid remote {key}')
    return result

def remote_only(old, new):
    if not old.get('kiosk') or not new.get('kiosk'):
        return False
    def stripped(c):
        c = copy.deepcopy(c)
        c['kiosk'].pop('remote', None)
        return c
    return old != new and stripped(old) == stripped(new)

def directory(name):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name):
        raise ValueError('Invalid container name')
    return ROOT / name

def write_policy(name, config):
    if 'kiosk' not in config:
        return
    parent = directory(name)
    parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    target = parent / 'sunshine.json'
    value = json.dumps(policy(config), sort_keys=True) + '\n'
    if target.exists() and target.read_text() == value:
        return
    fd, tmp = tempfile.mkstemp(dir=parent)
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(value)
            f.flush()
            os.fsync(f.fileno())
            os.fchmod(f.fileno(), 0o644)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def mounted_policy(name):
    """Only suppress native restart when the expected read-only policy bind exists."""
    source = str(directory(name))
    try:
        p = subprocess.run(['podman', 'inspect', name], capture_output=True, text=True,
                           timeout=3, check=True)
        item = json.loads(p.stdout)[0]
        return item['State']['Running'] and any(
            m.get('Source') == source and m.get('Destination') == DEST and not m.get('RW', True)
            for m in item.get('Mounts', []))
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError):
        return False

def verify_image(config):
    settings = config.get('kiosk', {})
    media = any(key in settings for key in ('video_decode', 'video_h264_buffers', 'video_av1_buffers'))
    if 'remote' not in settings and not media:
        return
    try:
        result = subprocess.run(['podman', 'image', 'inspect', config['image']],
                                capture_output=True, text=True, check=True, timeout=3)
        image = json.loads(result.stdout)[0]
        labels = image.get('Labels') or image.get('Config', {}).get('Labels') or {}
        if media and labels.get('io.vyarm.kiosk.media-policy') != '2':
            raise ValueError('Kiosk image lacks media CLI policy support (version 2)')
        for codec in ('h264', 'av1'):
            if settings.get(f'video_{codec}_buffers') == 'enabled' and labels.get(f'io.vyarm.kiosk.media-{codec}-reserve') != '1':
                raise ValueError(f'Kiosk image lacks validated {codec} capture reserve support')
        if 'remote' in settings and labels.get('io.vyarm.kiosk.sunshine-policy') != '1':
            raise ValueError('Kiosk image lacks Sunshine CLI policy support (version 1)')
    except (OSError, subprocess.SubprocessError, KeyError, IndexError) as error:
        raise ValueError('Cannot verify kiosk Sunshine policy image support') from error
