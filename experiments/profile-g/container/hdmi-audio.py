"""Select HDMI audio by the active DRM output's EDID, never probe every card."""
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import time


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


class AudioSession:
    def __init__(self, launch, children, drm, output):
        spec = importlib.util.spec_from_file_location('g_base_audio', '/opt/profile-g/kiosk-audio.py')
        base = importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
        runtime = Path(os.environ['XDG_RUNTIME_DIR'])
        script = runtime/'hdmi-pulse.pa'
        script.write_text('load-module module-native-protocol-unix\n'
                          'load-module module-null-sink sink_name=g_silent\n'
                          'set-default-sink g_silent\n')
        self.base = base.AudioSession(lambda args, **kw: launch(args + ['-n', '--file='+str(script)], **kw), children)
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
        device = select_device(self.drm, self.output)
        if device == self.device:
            return
        self.pactl('set-default-sink', 'g_silent')
        if self.module is not None:
            result = self.pactl('unload-module', self.module)
            if result is None or result.returncode:
                return
        self.module = self.device = None
        if device:
            # Timer scheduling avoided false ALSA POLLOUT wakeups in the ROCK
            # start/stop comparison and passed the HDMI A/V synchronization test.
            result = self.pactl('load-module', 'module-alsa-sink', 'device='+device,
                                'sink_name=g_hdmi', 'rate=48000', 'channels=2', 'tsched=1')
            if result is not None and result.returncode == 0:
                self.module, self.device = result.stdout.strip(), device
                self.pactl('set-default-sink', 'g_hdmi')
            else:
                # A bad/stale ELD must not cause rapid repeated ALSA opens.
                self.next_check = time.monotonic() + 30
        sink = 'g_hdmi' if self.device else 'g_silent'
        inputs = self.pactl('list', 'short', 'sink-inputs')
        if inputs is not None and inputs.returncode == 0:
            for line in inputs.stdout.splitlines():
                if line.split() and line.split()[0].isdigit():
                    self.pactl('move-sink-input', line.split()[0], sink)
        print(f'G HDMI audio: output={self.output} device={self.device or "silent (no matching audio display)"}', flush=True)
