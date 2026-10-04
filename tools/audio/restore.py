#!/usr/bin/python3
"""Initialize fresh mixers; use generic init only when a card has no UCM profile."""
import errno
import os
from pathlib import Path
import re
import subprocess
import sys

# libasound provides a precise ENOENT result, independent of translated messages.
PROBE = '''import ctypes, sys
lib = ctypes.CDLL('libasound.so.2')
manager = ctypes.c_void_p()
lib.snd_use_case_mgr_open.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_char_p]
result = lib.snd_use_case_mgr_open(ctypes.byref(manager), sys.argv[1].encode())
if result >= 0:
    lib.snd_use_case_mgr_close(manager)
print(result)
'''


def has_ucm(card):
    result = subprocess.run([sys.executable, '-c', PROBE, card],
                            capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise RuntimeError(result.stderr)
    code = int(result.stdout.strip())
    if code == -errno.ENOENT:
        return False
    if code < 0:
        raise RuntimeError(f'UCM probe for {card} failed ({code}): {result.stderr}')
    return True


def restore(sound=Path('/proc/asound'), state=Path('/var/lib/alsa/asound.state')):
    cards = sorted(p.name for p in sound.glob('card*') if re.fullmatch(r'card\d+', p.name))
    if not cards:
        return
    ucm_root = Path(os.environ.get('ALSA_CONFIG_UCM2', '/usr/share/alsa/ucm2'))
    if not (ucm_root/'ucm.conf').is_file():
        raise RuntimeError('Missing alsa-ucm-conf: refusing to treat missing package as missing card profile')
    fresh = not state.exists()
    for card in cards:
        device = 'hw:' + card[4:]
        ucm = has_ucm(device)
        print(f'ALSA {device}: {"UCM" if ucm else "generic (no UCM profile)"}; '
              f'{"initialize" if fresh else "restore"}', flush=True)
        args = ['/usr/sbin/alsactl'] + ([] if ucm else ['-U'])
        args += ['-f', str(state), 'init' if fresh else 'restore', card[4:]]
        result = subprocess.run(args, timeout=20)
        # Debian ALSA init/00main explicitly exits 99 after applying its
        # generic mixer defaults. This is not an I/O failure. Restore errors
        # and all other init failures must still propagate.
        if fresh and result.returncode == 99:
            print(f'ALSA {device}: generic mixer defaults applied (init status 99)', flush=True)
        else:
            result.check_returncode()
    if fresh:
        state.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['/usr/sbin/alsactl', '-f', str(state), 'store'], check=True, timeout=20)


if __name__ == '__main__':
    os.environ.update(HOME='/run/alsa', XDG_RUNTIME_DIR='/run/alsa/runtime', LC_ALL='C')
    try:
        restore()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'ALSA initialization failed: {error}', file=sys.stderr)
        sys.exit(1)
