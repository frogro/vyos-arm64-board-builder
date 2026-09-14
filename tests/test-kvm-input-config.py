#!/usr/bin/env python3
"""Config lifecycle checks without requiring a VyOS host."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch, call

ROOT = Path(__file__).resolve().parents[1]
class ConfigError(Exception):
    pass
vyos = types.ModuleType('vyos')
vyos.ConfigError = ConfigError
vyos.airbag = types.SimpleNamespace(enable=lambda: None)
config = types.ModuleType('vyos.config'); config.Config = object
configdict = types.ModuleType('vyos.configdict'); configdict.is_node_changed = lambda *_: True
with patch.dict(sys.modules, {'vyos': vyos, 'vyos.config': config, 'vyos.configdict': configdict}):
    spec = importlib.util.spec_from_file_location('kvm_config', ROOT / 'tools/kvm-cli/service_kvm_over_ip.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class Tests(unittest.TestCase):
    def test_rejects_missing_function_and_unstable_path(self):
        for c in [
            {'mouse': {'relative': {}}, 'local_input': {'keyboard': '/dev/input/by-id/test'}},
            {'keyboard': {}, 'local_input': {'mouse': '/dev/input/by-id/test'}},
            {'keyboard': {}, 'local_input': {'keyboard': '/dev/input/event0'}},
        ]:
            with self.subTest(c=c), self.assertRaises(ConfigError): m.verify(c)

    def test_absent_device_does_not_prevent_boot(self):
        with patch.object(m.os.path, 'isfile', return_value=True), patch.object(m, '_parse_provider_env', return_value={'KVM_GADGET_DEFAULT_PORT': 'dedicated'}):
            m.verify({'keyboard': {}, 'local_input': {'keyboard': '/dev/input/by-id/absent-device'}})

    def test_generate_and_delete_runtime_config(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.multiple(m, RUN_DIR=root, INPUT_CONFIG=root/'input.json', VIDEO_ENV=root/'video.env', MEDIAMTX_CONFIG=root/'media.yml'):
                m.generate({'keyboard': {}, 'local_input': {'keyboard': '/dev/input/by-id/test'}})
                self.assertEqual(json.loads(m.INPUT_CONFIG.read_text()), {'keyboard': '/dev/input/by-id/test'})
                self.assertEqual(m.INPUT_CONFIG.stat().st_mode & 0o777, 0o600)
                m.generate(None)
                self.assertFalse(m.INPUT_CONFIG.exists())

    def test_boot_stops_reader_before_gadget_and_starts_after(self):
        sequence = []
        with patch.object(m, '_systemctl', side_effect=lambda *a, **kw: sequence.append(a)), patch.object(m, '_apply_gadget', side_effect=lambda _: sequence.append(('gadget',))):
            m.apply({'keyboard': {}, '_video_changed': False, 'local_input': {'keyboard': '/dev/input/by-id/test'}})
        self.assertEqual(sequence, [('stop', m.INPUT_SERVICE), ('gadget',), ('restart', m.INPUT_SERVICE)])

    def test_delete_input_stops_only_reader(self):
        with patch.object(m, '_systemctl') as systemctl, patch.object(m, '_apply_gadget') as gadget:
            m.apply({'keyboard': {}, '_video_changed': False, '_gadget_changed': False, '_input_changed': True})
            systemctl.assert_called_once_with('stop', m.INPUT_SERVICE, check=True)
            gadget.assert_not_called()

    def test_unrelated_change_does_not_interrupt_input(self):
        with patch.object(m, '_systemctl') as systemctl, patch.object(m, '_apply_gadget') as gadget:
            m.apply({'keyboard': {}, '_video_changed': False, '_gadget_changed': False, '_input_changed': False, 'local_input': {'keyboard': '/dev/input/by-id/test'}})
            systemctl.assert_not_called(); gadget.assert_not_called()

if __name__ == '__main__': unittest.main()
