#!/usr/bin/env python3
"""Supervise the experimental kiosk desktop and terminate all children on stop."""
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import time

spec = importlib.util.spec_from_file_location('display', '/usr/local/bin/kiosk-display.py')
display = importlib.util.module_from_spec(spec)
spec.loader.exec_module(display)
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
    _, _, url = display.settings(os.environ)
    display.configure()
    subprocess.run(['xset', 's', 'off'], check=True)
    subprocess.run(['xset', '-dpms'], check=False)
    config = Path.home() / '.config'
    (config / 'openbox').mkdir(parents=True, exist_ok=True)
    if Path('/state/openbox/rc.xml').exists():
        link('/state/openbox/rc.xml', config / 'openbox/rc.xml')
    link('/state/sunshine', config / 'sunshine')
    os.environ['LANG'] = 'C.UTF-8'
    with open('/state/sunshine/runtime.log', 'w') as log:
        sunshine = launch(['sunshine', '/state/sunshine/sunshine.conf'], stdout=log, stderr=subprocess.STDOUT)
        wm = launch(['openbox'])
        touch = launch(['python3', '/usr/local/bin/kiosk-display.py', 'watch'])
        browser = None
        retry = 0
        while not stopping:
            if wm.poll() is not None or touch.poll() is not None:
                raise RuntimeError('Kiosk window manager or touch monitor stopped')
            if browser is not None and browser.poll() is not None:
                children.remove(browser)
                browser = None
                retry = time.monotonic() + 2
            if browser is None and time.monotonic() >= retry:
                browser = launch(['chromium', '--kiosk', '--no-first-run',
                                  '--disable-session-crashed-bubble',
                                  '--disable-features=Translate,TranslateUI',
                                  '--user-data-dir=/state/browser', url])
            time.sleep(.2)
finally:
    # A bounded stop also handles Chromium descendants and an already-exited parent.
    for child in children:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 5
    for child in children:
        try:
            child.wait(timeout=max(.01, deadline-time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
    for child in children:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    for child in children:
        child.wait()
