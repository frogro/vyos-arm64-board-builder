import importlib.util
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
bridge = load('bridge', BASE / 'sunshine/input-bridge/bridge.py')
remote = load('remote_bridge', BASE / 'cli/remote.py')
kiosk = load('kiosk_bridge', BASE / 'cli/kiosk.py')

class InputBridgeTests(unittest.TestCase):
    def test_real_udev_header_retained_on_remove(self):
        body = b'ACTION=add\0DEVNAME=/dev/input/event6\0DEVPATH=/devices/virtual/input/input12/event6\0'
        header = bytearray(40)
        header[:8] = b'libudev\0'
        struct.pack_into('=II', header, 16, 40, len(body))
        data = bytes(header) + body
        removed = bridge.removal(data)
        self.assertEqual(bridge.properties(removed)[b'ACTION'], b'remove')
        self.assertEqual(bridge.properties(removed)[b'DEVPATH'], bridge.properties(data)[b'DEVPATH'])
        self.assertEqual(removed[24:40], data[24:40])
        self.assertEqual(bridge.properties(data[:-4]), {})
        self.assertEqual(bridge.properties(b'add@/devices/input\0'), {})

    def test_policy_and_backend_both_required(self):
        info = [{'Config': {'Env': ['KIOSK_DISPLAY_BACKEND=wayland']}}]
        policy = {'version': 1, 'access': 'enabled', 'input': 'control'}
        with patch.object(bridge, 'run', return_value=json.dumps(info).encode()), patch.object(Path, 'read_text', return_value=json.dumps(policy)):
            self.assertTrue(bridge.control_enabled('kiosk'))
            self.assertFalse(bridge.control_enabled('../kiosk'))
        for disabled in ({}, dict(policy, input='view-only'), dict(policy, access='disabled')):
            with patch.object(bridge, 'run', return_value=json.dumps(info).encode()), patch.object(Path, 'read_text', return_value=json.dumps(disabled)):
                self.assertFalse(bridge.control_enabled('kiosk'))
        with patch.object(bridge, 'run', return_value=b'[{"Config":{"Env":["KIOSK_DISPLAY_BACKEND=x11"]}}]'), patch.object(Path, 'read_text', return_value=json.dumps(policy)):
            self.assertFalse(bridge.control_enabled('kiosk'))

    def test_ownership_requires_uinput_fd_not_device_name(self):
        with patch.object(bridge.os, 'pidfd_open', return_value=123), patch.object(bridge.os, 'close'), patch.object(Path, 'iterdir', return_value=[Path('/proc/99/fd/4')]), patch.object(bridge.os, 'readlink', return_value='/dev/input/event4'), patch.object(bridge.LIBC, 'syscall') as syscall:
            self.assertEqual(bridge.owned_inputs(99), {})
            syscall.assert_not_called()

    def test_cgroup_rule_only_for_wayland_control(self):
        def cfg(backend, access, inp):
            return {'kiosk': {'url': 'file:///opt/kiosk/input-test.html', 'display_backend': backend,
                              'remote': {'access': access, 'input': inp}}}
        enabled = cfg('wayland', 'enabled', 'control')
        self.assertIn('PodmanArgs=--device-cgroup-rule="c 13:* rw"', kiosk.environment(enabled))
        for other in (cfg('x11','enabled','control'), cfg('wayland','disabled','control'), cfg('wayland','enabled','view-only')):
            self.assertFalse(any('device-cgroup-rule' in x for x in kiosk.environment(other)))
        view = cfg('wayland','enabled','view-only')
        self.assertFalse(remote.remote_only(view, enabled))
        audio = cfg('wayland','enabled','control')
        audio['kiosk']['remote']['audio'] = 'enabled'
        self.assertTrue(remote.remote_only(enabled, audio))

if __name__ == '__main__':
    unittest.main()
