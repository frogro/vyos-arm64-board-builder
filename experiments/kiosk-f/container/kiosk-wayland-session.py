#!/usr/bin/env python3
"""Supervise the experimental kiosk desktop and terminate all children on stop."""
import importlib.util
import os
from pathlib import Path
import signal
import select
import subprocess
import time

spec = importlib.util.spec_from_file_location('display', '/usr/local/bin/kiosk-display.py')
display = importlib.util.module_from_spec(spec)
spec.loader.exec_module(display)
media_spec = importlib.util.spec_from_file_location('media', '/usr/local/bin/kiosk-media.py')
media = importlib.util.module_from_spec(media_spec)
media_spec.loader.exec_module(media)
audio_spec = importlib.util.spec_from_file_location('audio', '/usr/local/bin/kiosk-audio.py')
audio_module = importlib.util.module_from_spec(audio_spec)
audio_spec.loader.exec_module(audio_module)
schedule_spec = importlib.util.spec_from_file_location('schedule', '/usr/local/bin/kiosk-schedule.py')
schedule_module = importlib.util.module_from_spec(schedule_spec)
schedule_spec.loader.exec_module(schedule_module)
children = []
stopping = False


def stop(_signum, _frame):
    global stopping
    stopping = True


def launch(args, **kwargs):
    proc = subprocess.Popen(args, start_new_session=True, **kwargs)
    children.append(proc)
    return proc


def link(source, target):
    if target.is_symlink():
        target.unlink()
    elif target.exists():
        raise RuntimeError(f'Refusing to replace existing {target}')
    target.symlink_to(source)


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
try:
    # Own the session bus directly, so the root starter signals this supervisor,
    # not runuser/dbus-run-session which can exit before desktop cleanup finishes.
    bus = launch(['dbus-daemon', '--session', '--nofork', '--print-address=1'],
                 stdout=subprocess.PIPE, text=True)
    ready, _, _ = select.select([bus.stdout], [], [], 5)
    if not ready:
        raise RuntimeError('Session bus did not become ready')
    address = bus.stdout.readline().strip()
    if not address or bus.poll() is not None:
        raise RuntimeError('Session bus failed to start')
    os.environ['DBUS_SESSION_BUS_ADDRESS'] = address
    _, _, url = display.settings(os.environ)
    config = Path.home() / '.config'
    (config / 'openbox').mkdir(parents=True, exist_ok=True)
    if Path('/state/openbox/rc.xml').exists():
        link('/state/openbox/rc.xml', config / 'openbox/rc.xml')
    link('/state/sunshine', config / 'sunshine')
    os.environ['LANG'] = 'C.UTF-8'
    audio = audio_module.AudioSession(launch, children)
    audio.start()
    with open('/state/sunshine/supervisor.log', 'w') as log:
        sunshine = launch(['python3', '/usr/local/bin/kiosk-sunshine.py', 'serve'], stdout=log, stderr=subprocess.STDOUT)
        wm = None
        touch = None
        remote_retry = 0
        browser = None
        scheduled_active = None
        retry = 0
        while not stopping:
            audio.tick()
            if sunshine is not None and sunshine.poll() is not None:
                children.remove(sunshine)
                sunshine = None
                remote_retry = time.monotonic() + 5
            if sunshine is None and time.monotonic() >= remote_retry:
                sunshine = launch(['python3', '/usr/local/bin/kiosk-sunshine.py', 'serve'], stdout=log, stderr=subprocess.STDOUT)
            active_now = schedule_module.active(os.environ)
            if scheduled_active is not None and active_now != scheduled_active and browser is not None:
                try:os.killpg(browser.pid, signal.SIGTERM)
                except ProcessLookupError:pass
                try:browser.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:os.killpg(browser.pid, signal.SIGKILL)
                    except ProcessLookupError:pass
                    browser.wait(timeout=3)
                children.remove(browser)
                browser = None
            if scheduled_active != active_now:
                status_path = Path('/run/kiosk/schedule.json')
                temporary = status_path.with_suffix('.tmp')
                temporary.write_text(__import__('json').dumps({'active':active_now,'mode':'browser blanking; no CEC power control'}))
                temporary.replace(status_path)
            scheduled_active = active_now
            if browser is not None and browser.poll() is not None:
                children.remove(browser)
                browser = None
                retry = time.monotonic() + 2
            if browser is None and time.monotonic() >= retry:
                media_args, media_status = media.browser_policy(os.environ)
                media_args = media.merge_arguments(['--ozone-platform=wayland'], media_args, media_status)
                browser = launch([media_status['executable'], '--kiosk', '--no-first-run',
                                  '--disable-session-crashed-bubble',
                                  '--autoplay-policy=no-user-gesture-required',
                                  '--disable-features=Translate,TranslateUI',
                                  '--user-data-dir=/state/browser'] + (['--remote-debugging-address=127.0.0.1', '--remote-debugging-port=9225'] if scheduled_active and url == 'http://127.0.0.1:8089/player' else []) + (['--mute-audio'] if os.environ.get('KIOSK_AUDIO_MUTED') == 'enabled' else []) + media_args + [url if scheduled_active else 'data:text/html,<html style="background:black"></html>'])
            time.sleep(.2)
finally:
    bus_process = children.pop(0) if children and 'bus' in globals() and children[0] is bus else None
    # A bounded stop also handles Chromium descendants and an already-exited parent.
    for child in reversed(children):
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 30
    for child in reversed(children):
        try:
            child.wait(timeout=max(.01, deadline-time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
    for child in reversed(children):
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    for child in reversed(children):
        child.wait()
    if bus_process is not None:
        bus_process.terminate()
        try:
            bus_process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            bus_process.kill()
            bus_process.wait()
    print('Kiosk desktop children stopped', flush=True)
