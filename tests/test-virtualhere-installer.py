#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installer', ROOT/'experiments/profile-e/cli/install-virtualhere.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class Installation(unittest.TestCase):
    def test_corrupt_download_does_not_replace_existing_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root/'vhusbdarm64'
            binary.write_bytes(b'existing')
            with self.assertRaises(ValueError):
                m.install(b'corrupt or new unreviewed version',root)
            self.assertEqual(binary.read_bytes(),b'existing')
            self.assertFalse((root/'installation.json').exists())
    def test_verified_install_preserves_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'vhusbdarm64').write_bytes(b'previous')
            with patch.object(m,'validate'):
                dest=m.install(b'test-verified-payload',root)
            self.assertEqual(dest.read_bytes(),b'test-verified-payload')
            self.assertEqual((root/'vhusbdarm64.previous').read_bytes(),b'previous')
            self.assertEqual(dest.stat().st_mode & 0o777,0o700)
            self.assertEqual(root.stat().st_mode & 0o777,0o700)

if __name__=='__main__':unittest.main()
