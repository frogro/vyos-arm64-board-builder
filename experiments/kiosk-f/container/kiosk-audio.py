#!/usr/bin/env python3
"""Keep a private per-kiosk PulseAudio session for browser and Sunshine audio."""
import os
from pathlib import Path
import shutil
import subprocess
import time


class AudioSession:
    def __init__(self, launch, children):
        self.launch = launch
        self.children = children
        self.process = None
        self.retry = 0
        self.available = bool(shutil.which('pulseaudio') and shutil.which('pactl'))
        runtime = Path(os.environ['XDG_RUNTIME_DIR']) / 'pulse'
        runtime.mkdir(mode=0o700, exist_ok=True)
        os.environ['PULSE_SERVER'] = 'unix:' + str(runtime / 'native')

    def tick(self):
        if not self.available:
            return
        if self.process is not None and self.process.poll() is None:
            return
        if time.monotonic() < self.retry:
            return
        if self.process is not None:
            self.children.remove(self.process)
        try:
            self.process = self.launch(['pulseaudio', '--daemonize=no', '--exit-idle-time=-1',
                                        '--log-target=stderr'])
        except OSError as error:
            self.available = False
            print(f'Kiosk audio unavailable: {error}', flush=True)
            return
        self.retry = time.monotonic() + 10

    def start(self):
        self.tick()
        # Bounded initialization. Missing audio must not prevent local display.
        for _ in range(30):
            if not self.available or self.process.poll() is not None:
                break
            try:
                ready = subprocess.run(['pactl', 'info'], stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, timeout=2).returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                break
            if ready:
                print('Kiosk PulseAudio ready', flush=True)
                return
            time.sleep(.1)
        print('Kiosk audio unavailable; display continues', flush=True)
