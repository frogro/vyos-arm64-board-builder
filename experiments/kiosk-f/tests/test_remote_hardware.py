import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

P = Path(__file__).resolve().parents[1] / 'systemd/remote-hardware.py'
spec = importlib.util.spec_from_file_location('hardware', P)
hardware = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hardware)

class RestoreTest(unittest.TestCase):
    def test_restore_previous_value_not_assumed_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            param, saved = Path(tmp)/'param', Path(tmp)/'saved'
            with patch.object(hardware, 'PARAM', param), patch.object(hardware, 'SAVED', saved):
                for before in ('Y', 'N'):
                    param.write_text('Y'); saved.write_text(before)
                    hardware.restore()
                    self.assertEqual(param.read_text(), before)
                    self.assertFalse(saved.exists())
