#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('input_bridge', ROOT / 'tools/kvm-cli/vyos-kvm-input.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Tests(unittest.TestCase):
    def test_modifier_press_repeat_and_release(self):
        k = m.Keyboard()
        self.assertEqual(k.update(42, 1)[0], 2)
        self.assertEqual(k.update(30, 1), bytes([2,0,4,0,0,0,0,0]))
        self.assertIsNone(k.update(30, 2))
        self.assertEqual(k.update(30, 0), bytes([2,0,0,0,0,0,0,0]))
        self.assertEqual(k.update(42, 0), bytes(8))

    def test_power_key_never_forwarded(self):
        self.assertIsNone(m.Keyboard().update(116, 1))

    def test_rollover_recovers_after_key_release(self):
        k = m.Keyboard()
        for code in range(16, 23):
            report = k.update(code, 1)
        self.assertEqual(report[2:], bytes([1]*6))
        self.assertNotEqual(k.update(22, 0)[2:], bytes([1]*6))

    def test_large_mouse_motion_preserves_distance_and_button_state(self):
        mouse = m.Mouse()
        mouse.update(1,272,1)
        mouse.update(2,0,300)
        mouse.update(2,1,-260)
        reports = [struct.unpack('<Bbbb', r) for r in mouse.update(0,0,0)]
        self.assertEqual(sum(r[1] for r in reports), 300)
        self.assertEqual(sum(r[2] for r in reports), -260)
        self.assertTrue(all(r[0]==1 for r in reports))
        mouse.update(1,272,0)
        self.assertEqual(mouse.update(0,0,0), [bytes(4)])

    def test_close_releases_pressed_keys_even_if_host_disconnected(self):
        f = m.Forwarder.__new__(m.Forwarder)
        f.kind, f.source, f.target = 'keyboard', 101, 102
        with patch.object(m, 'write_report', side_effect=TimeoutError) as write, patch.object(m.os, 'close') as close:
            f.close()
            write.assert_called_once_with(102, bytes(8))
            self.assertEqual([c.args[0] for c in close.call_args_list], [101,102])
        self.assertIsNone(f.source)
        self.assertIsNone(f.target)

    def test_dropped_input_forces_release_and_reacquire(self):
        f = m.Forwarder.__new__(m.Forwarder)
        f.source = 10
        with patch.object(m.os, 'read', return_value=m.EVENT.pack(0,0,0,3,0)):
            with self.assertRaises(OSError):
                f.read()

    def test_unplug_does_not_keep_old_key_state(self):
        f = m.Forwarder.__new__(m.Forwarder)
        f.source = 10
        with patch.object(m.os, 'read', return_value=b''):
            with self.assertRaises(OSError):
                f.read()

    def test_non_usb_input_rejected(self):
        with patch.object(m.Path, 'resolve', return_value=Path('/dev/input/event1')), patch.object(m.Path, 'read_text', return_value='0019'):
            with self.assertRaises(ValueError):
                m.input_node('/dev/input/by-id/example')

if __name__ == '__main__':
    unittest.main()
