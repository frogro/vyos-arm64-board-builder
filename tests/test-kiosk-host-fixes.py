#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'experiments/kiosk-f/host/install.py'
spec = importlib.util.spec_from_file_location('hostfix', SOURCE)
fix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fix)

class HostFixTests(unittest.TestCase):
    def test_other_gpu_does_not_fetch_mali(self):
        with tempfile.TemporaryDirectory() as root:
            fix.install(root, '/nonexistent-cache', False)
            self.assertFalse((Path(root) / 'usr/lib/firmware').exists())
            dropin = Path(root) / 'etc/systemd/system/rsyslog.service.d/50-vyarm-config-ready.conf'
            self.assertIn('ConditionPathExists=/run/rsyslog/rsyslog.conf', dropin.read_text())

    def test_corrupt_firmware_rejected_before_install(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as cache:
            (Path(cache) / 'mali_csffw.bin').write_bytes(b'corrupted download')
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                fix.install(root, cache, True)
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_symlink_cannot_escape_staging_root(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as other:
            (Path(root) / 'etc').symlink_to(other)
            with self.assertRaisesRegex(ValueError, 'escapes root'):
                fix.install(root, '/nonexistent', False)
            self.assertEqual(list(Path(other).iterdir()), [])

if __name__ == '__main__':
    unittest.main()
