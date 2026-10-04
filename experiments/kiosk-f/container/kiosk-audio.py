#!/usr/bin/env python3
"""Keep a private per-kiosk PulseAudio session for browser and Sunshine audio."""
import os
import json
import re
from pathlib import Path
import shutil
import subprocess
import time


class PulseSession:
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
            if not self.available or self.process is None or self.process.poll() is not None:
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


def select_device(drm, output, drm_root=Path('/sys/class/drm'), sound_root=Path('/proc/asound')):
    connector = drm_root / (drm + '-' + output)
    try:
        if (connector/'status').read_text().strip() != 'connected':
            return None
        edid = (connector/'edid').read_bytes()
    except OSError:
        return None
    if len(edid) < 128 or edid[:8] != b'\x00\xff\xff\xff\xff\xff\xff\x00':
        return None
    vendor, product = int.from_bytes(edid[8:10], 'little'), int.from_bytes(edid[10:12], 'little')
    matches = []
    for card in sound_root.glob('card[0-9]*'):
        if not re.fullmatch(r'card\d+', card.name):
            continue
        # A single playback PCM can be mapped unambiguously to this card's ELD.
        pcms = list(card.glob('pcm*p'))
        if len(pcms) != 1 or not re.fullmatch(r'pcm\d+p', pcms[0].name):
            continue
        for eld in card.glob('eld*'):
            try:
                fields = dict(line.split(None, 1) for line in eld.read_text().splitlines() if len(line.split(None, 1)) == 2)
                if (int(fields.get('manufacture_id', '-1'), 0) == vendor and
                    int(fields.get('product_id', '-1'), 0) == product and
                    int(fields.get('sad_count', '0')) > 0 and
                    fields.get('eld_version', '').split()[0:1] in (['[0x2]'], ['[0x02]'])):
                    matches.append('plughw:' + card.name[4:] + ',' + pcms[0].name[3:-1])
                    break
            except (OSError, ValueError):
                continue
    # Identical monitors on multiple cards are ambiguous: stay silent, never guess.
    return matches[0] if len(matches) == 1 else None


def kiosk_connector(drm_root=Path('/sys/class/drm')):
    """Resolve the selected compositor output without assuming a card number."""
    requested = os.environ.get('KIOSK_OUTPUT', 'auto')
    for status in (Path(os.environ.get('XDG_RUNTIME_DIR', '/run/kiosk'))/'display.json',
                   Path('/run/kiosk/display.json')):
        try:
            requested = json.loads(status.read_text()).get('output', requested)
            break
        except (OSError, ValueError):
            pass
    # Xorg modesetting calls DRM HDMI-A-1 HDMI-1.
    requested = re.sub(r'^HDMI-(\d+)$', r'HDMI-A-\1', requested)
    candidates = []
    for connector in drm_root.glob('card*-*'):
        match = re.fullmatch(r'(card\d+)-(.+)', connector.name)
        if not match or (requested != 'auto' and requested != match[2]):
            continue
        try:
            if (connector/'status').read_text().strip() == 'connected':
                candidates.append((match[1], match[2]))
        except OSError:
            pass
    return candidates[0] if len(candidates) == 1 else (None, None)


class AudioSession:
    def __init__(self, launch, children, drm=None, output=None):
        runtime = Path(os.environ['XDG_RUNTIME_DIR'])
        script = runtime/'hdmi-pulse.pa'
        script.write_text('load-module module-native-protocol-unix\n'
                          'load-module module-null-sink sink_name=vyarm_silent\n'
                          'set-default-sink vyarm_silent\n')
        self.base = PulseSession(lambda args, **kw: launch(args + ['-n', '--file='+str(script)], **kw), children)
        self.drm, self.output = drm, output
        self.module = None
        self.device = None
        self.next_check = 0
        self.server = None

    @property
    def process(self):
        return self.base.process

    def pactl(self, *args):
        try:
            return subprocess.run(['pactl', *args], capture_output=True, text=True, timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            return None

    def start(self):
        self.base.start()
        self.tick()

    def tick(self):
        self.base.tick()
        if self.process is None or self.process.poll() is not None:
            return
        if time.monotonic() < self.next_check:
            return
        self.next_check = time.monotonic() + 2
        if self.server is not self.process:
            self.server = self.process
            self.module = self.device = None
        drm, output = (self.drm, self.output) if self.drm and self.output else kiosk_connector()
        device = select_device(drm, output) if drm and output else None
        if device == self.device:
            return
        self.pactl('set-default-sink', 'vyarm_silent')
        if self.module is not None:
            result = self.pactl('unload-module', self.module)
            if result is None or result.returncode:
                return
        self.module = self.device = None
        if device:
            # Timer scheduling avoided false ALSA POLLOUT wakeups in the ROCK
            # start/stop comparison and passed the HDMI A/V synchronization test.
            result = self.pactl('load-module', 'module-alsa-sink', 'device='+device,
                                'sink_name=vyarm_hdmi', 'rate=48000', 'channels=2', 'tsched=1')
            if result is not None and result.returncode == 0:
                self.module, self.device = result.stdout.strip(), device
                self.pactl('set-default-sink', 'vyarm_hdmi')
            else:
                # A bad/stale ELD must not cause rapid repeated ALSA opens.
                self.next_check = time.monotonic() + 30
        sink = 'vyarm_hdmi' if self.device else 'vyarm_silent'
        inputs = self.pactl('list', 'short', 'sink-inputs')
        if inputs is not None and inputs.returncode == 0:
            for line in inputs.stdout.splitlines():
                if line.split() and line.split()[0].isdigit():
                    self.pactl('move-sink-input', line.split()[0], sink)
        print(f'Display HDMI audio: output={output or "unresolved"} device={self.device or "silent (no matching audio display)"}', flush=True)
