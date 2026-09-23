#!/usr/bin/env python3
"""Own DRM Weston lifecycle. Browser stays unprivileged and sandboxed."""
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import signal
import subprocess
import time


def output_config(outputs, requested, rotation):
    transforms = {'0': 'normal', '90': 'rotate-270', '180': 'rotate-180', '270': 'rotate-90'}
    if rotation not in transforms:
        raise ValueError('Invalid rotation')
    if requested == 'auto':
        if len(outputs) != 1:
            raise ValueError('Wayland auto output requires exactly one connected display')
        selected = outputs[0]
    else:
        # Preserve the CLI's legacy Xorg HDMI-1 names on the DRM path.
        selected = re.sub(r'^HDMI-(\d+)$', r'HDMI-A-\1', requested)
        if selected not in outputs:
            raise ValueError('Requested DRM output is not connected')
    text = '[core]\nidle-time=0\nshell=kiosk-shell.so\nrequire-input=false\n\n[keyboard]\nkeymap_layout=de\n'
    for output in outputs:
        text += f'\n[output]\nname={output}\nmode={"preferred" if output == selected else "off"}\n'
        if output == selected:
            text += f'transform={transforms[rotation]}\n'
    return text, selected


def main():
    runtime = Path('/run/kiosk')
    runtime.mkdir(exist_ok=True)
    for directory in ['browser', 'sunshine', 'cache']:
        (Path('/state') / directory).mkdir(parents=True, exist_ok=True)
    lock = open('/state/kiosk-session.lock', 'w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for name in ('SingletonLock', 'SingletonSocket', 'SingletonCookie'):
        (Path('/state/browser') / name).unlink(missing_ok=True)
    user = pwd.getpwnam('kiosk')
    subprocess.run(['chown', '-R', 'kiosk:kiosk', '/state', str(runtime)], check=True)
    os.chmod(runtime, 0o700)
    outputs = []
    for status in Path('/sys/class/drm').glob('card0-*/status'):
        if status.read_text().strip() == 'connected':
            name = re.sub(r'^card[0-9]+-', '', status.parent.name)
            if re.fullmatch(r'[A-Za-z0-9_.-]+', name):
                outputs.append(name)
    text, selected = output_config(sorted(set(outputs)), os.environ.get('KIOSK_OUTPUT', 'auto'), os.environ.get('KIOSK_ROTATION', '0'))
    config = runtime / 'weston.ini'
    config.write_text(text)
    # Only explicitly granted devices contribute groups. No host-wide permissions.
    nodes = list(Path('/dev/dri').glob('*')) + list(Path('/dev').glob('video*')) + list(Path('/dev').glob('media*'))
    groups = sorted(set(os.getgrouplist('kiosk', user.pw_gid)) | {p.stat().st_gid for p in nodes if p.is_char_device() and p.stat().st_gid != 0})
    env = dict(os.environ, XDG_RUNTIME_DIR=str(runtime), WAYLAND_DISPLAY='wayland-kiosk', LIBSEAT_BACKEND='builtin', SEATD_VTBOUND='0')
    children = []
    def stop(*_):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        weston = subprocess.Popen(['/usr/bin/weston', '--backend=drm', '--drm-device=card0', '--renderer=gl', '--config='+str(config), '--socket=wayland-kiosk', '--log=/state/weston.log'], env=env, start_new_session=True)
        children.append(weston)
        for _ in range(100):
            if weston.poll() is not None:
                raise RuntimeError('Weston failed; see /state/weston.log; select x11 to fall back')
            if (runtime / 'wayland-kiosk').is_socket():
                break
            time.sleep(.1)
        else:
            raise RuntimeError('Wayland socket timeout')
        os.chown(runtime / 'wayland-kiosk', user.pw_uid, user.pw_gid)
        (runtime / 'display.json').write_text(json.dumps({'backend':'wayland','output':selected,'rotation':os.environ.get('KIOSK_ROTATION','0'),'touch':'libinput: physical test required'}))
        env.update(HOME='/home/kiosk', XDG_CACHE_HOME='/state/cache')
        session = subprocess.Popen(['setpriv','--reuid','kiosk','--regid','kiosk','--groups',','.join(map(str,groups)),'python3','/usr/local/bin/kiosk-wayland-session.py'], env=env, start_new_session=True)
        children.append(session)
        while weston.poll() is None and session.poll() is None:
            time.sleep(.25)
        raise RuntimeError('Wayland compositor or browser session stopped')
    except KeyboardInterrupt:
        pass
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        for child in reversed(children):
            try: os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError: pass
        for child in reversed(children):
            try: child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL); child.wait()


if __name__ == '__main__':
    main()
