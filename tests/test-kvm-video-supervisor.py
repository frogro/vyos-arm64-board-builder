#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('supervisor', ROOT / 'tools/kvm-cli/vyos-kvm-video-supervisor.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Event:
    def __init__(self, limit):
        self.tick = 0
        self.limit = limit
    def is_set(self):
        return self.tick >= self.limit
    def wait(self, timeout):
        self.tick += 1


class Child:
    def poll(self):
        return None


class Tests(unittest.TestCase):
    def run_sequence(self, signals, readiness=True, health=True):
        event = Event(len(signals))
        launches, stops = [], []
        def launch(*args, **kwargs):
            child = Child()
            launches.append((child, kwargs))
            return child
        m.supervise('/dev/video1', 'ffmpeg', '/runner', event,
                    detect=lambda _: ((('mode', signals[event.tick]),) if signals[event.tick] else None), ready=lambda: readiness,
                    healthy=lambda: health, launch=launch, stop=lambda p: stops.append(p) if p else None,
                    clock=lambda: event.tick * 10)
        return launches, stops

    def test_clock_measurement_jitter_does_not_restart(self):
        a = (('Active width', '1920'), ('Pixelclock', '148496000 Hz (60.00 frames per second)'))
        b = (('Active width', '1920'), ('Pixelclock', '148500000 Hz (60.00 frames per second)'))
        self.assertTrue(m.same_timings(a, b))
        self.assertFalse(m.same_timings(a, (('Active width', '1280'),)))

    def test_no_signal_does_not_start_encoder(self):
        self.assertEqual(self.run_sequence([None] * 5)[0], [])

    def test_wait_for_transport(self):
        self.assertEqual(self.run_sequence(['1080p'] * 4, readiness=False)[0], [])

    def test_loss_return_and_changed_timings_restart(self):
        launches, stops = self.run_sequence(['1080p', '1080p', None, None, '1080p', '720p'])
        self.assertEqual(len(launches), 3)
        self.assertEqual(len(stops), 3)
        self.assertTrue(all(k['start_new_session'] for _, k in launches))
        self.assertTrue(all(k['env']['KVM_VIDEO_SUPERVISED'] == '1' for _, k in launches))

    def test_live_process_with_dead_stream_restarts(self):
        launches, _ = self.run_sequence(['1080p'] * 6, health=False)
        self.assertEqual(len(launches), 2)

    def test_healthy_stream_not_restarted(self):
        self.assertEqual(len(self.run_sequence(['1080p'] * 9)[0]), 1)

    @patch.object(m.subprocess, 'run')
    def test_absent_power_skips_noisy_timing_query(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, 'power_present: 0\n', '')
        self.assertIsNone(m.detected_timings('/dev/video1'))
        self.assertEqual(run.call_count, 1)

    @patch.object(m.subprocess, 'run')
    def test_rtsp_metadata_without_packets_not_healthy(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, '{"streams":[{"codec_type":"video","nb_read_packets":"0"}]}', '')
        self.assertFalse(m.stream_healthy())

    def test_hid_enable_returns_success_when_initially_unbound(self):
        script = (ROOT / 'tools/common-firstboot/vyos-kvm-gadget').read_text()
        for name in ('keyboard_enable', 'mouse_absolute_enable', 'mouse_relative_enable'):
            start = script.index(name + '()\n')
            function = script[start:script.index('\n}\n', start) + 3]
            stub = '''set -e
GADGET=/nonexistent-test-gadget
load_provider() { :; }
ensure_runtime() { :; }
create_base() { :; }
ensure_keyboard() { :; }
ensure_absolute_mouse() { :; }
ensure_relative_mouse() { :; }
bind_gadget() { return 99; }
'''
            subprocess.run(['bash', '-c', stub + function + '\n' + name], check=True)

if __name__ == '__main__':
    unittest.main()
