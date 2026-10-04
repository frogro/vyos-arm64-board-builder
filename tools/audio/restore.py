#!/usr/bin/python3
"""Initialize fresh mixers; use generic init only when a card has no UCM profile."""
import argparse
import ctypes
import fcntl
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


def saved_card(state, card_id):
    """Parse ALSA's own format; distinguish a missing card from corrupt state."""
    if not state.exists():
        return False
    lib = ctypes.CDLL('libasound.so.2')
    pointer = ctypes.c_void_p
    lib.snd_input_stdio_open.argtypes = [ctypes.POINTER(pointer), ctypes.c_char_p, ctypes.c_char_p]
    lib.snd_config_top.argtypes = [ctypes.POINTER(pointer)]
    lib.snd_config_load.argtypes = [pointer, pointer]
    lib.snd_config_search.argtypes = [pointer, ctypes.c_char_p, ctypes.POINTER(pointer)]
    config, source, result = pointer(), pointer(), pointer()
    def check(code):
        if code < 0:
            raise RuntimeError(f'Cannot parse ALSA state {state}: {code}')
    check(lib.snd_input_stdio_open(ctypes.byref(source), os.fsencode(state), b'r'))
    try:
        check(lib.snd_config_top(ctypes.byref(config)))
        try:
            check(lib.snd_config_load(config, source))
            code = lib.snd_config_search(config, ('state.'+card_id).encode(), ctypes.byref(result))
            if code == -errno.ENOENT:
                return False
            check(code)
            return True
        finally:
            lib.snd_config_delete(config)
    finally:
        lib.snd_input_close(source)


def restore(sound=Path('/proc/asound'), state=Path('/var/lib/alsa/asound.state'), selected=None):
    cards = sorted(p.name for p in sound.glob('card*') if re.fullmatch(r'card\d+', p.name))
    if selected is not None:
        cards = [c for c in cards if c == 'card'+selected]
    if not cards:
        return
    ucm_root = Path(os.environ.get('ALSA_CONFIG_UCM2', '/usr/share/alsa/ucm2'))
    if not (ucm_root/'ucm.conf').is_file():
        raise RuntimeError('Missing alsa-ucm-conf: refusing to treat missing package as missing card profile')
    for card in cards:
        device = 'hw:' + card[4:]
        fresh = not saved_card(state, (sound/card/'id').read_text().strip())
        ucm = has_ucm(device)
        print(f'ALSA {device}: {"UCM" if ucm else "generic (no UCM profile)"}; '
              f'{"initialize" if fresh else "restore"}', flush=True)
        args = ['/usr/sbin/alsactl'] + ([] if ucm else ['-U'])
        args += ['-f', str(state), 'init' if fresh else 'restore', card[4:]]
        result = subprocess.run(args, timeout=20)
        # Debian init/00main explicitly exits 99 after applying generic defaults.
        if fresh and result.returncode == 99:
            print(f'ALSA {device}: generic mixer defaults applied (init status 99)', flush=True)
        else:
            result.check_returncode()
        if fresh:
            state.parent.mkdir(parents=True, exist_ok=True)
            # alsactl merges this card into the file, retaining other card states.
            subprocess.run(['/usr/sbin/alsactl', '-f', str(state), 'store', card[4:]], check=True, timeout=20)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--card', type=str)
    parser.add_argument('--store', action='store_true')
    args = parser.parse_args()
    selected = args.card
    if selected is not None:
        selected = selected.removeprefix('controlC')
        if not selected.isdecimal():
            parser.error('card must be a card number or controlC<number>')
    os.environ.update(HOME='/run/alsa', XDG_RUNTIME_DIR='/run/alsa/runtime', LC_ALL='C')
    Path('/run/alsa').mkdir(parents=True, exist_ok=True)
    # Both boot paths, hotplug and shutdown share this lock.
    with open('/run/alsa/vyarm-restore.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.store:
            subprocess.run(['/usr/sbin/alsactl', 'store'], check=True, timeout=20)
        else:
            restore(selected=selected)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'ALSA initialization failed: {error}', file=sys.stderr)
        sys.exit(1)
