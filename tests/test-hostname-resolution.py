#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('patcher', ROOT / 'tools/patch-vyos-hostname-resolution.py')
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)

class HostnameResolution(unittest.TestCase):
    def setup_root(self, root, content, library=True):
        (root / 'etc').mkdir()
        p = root / 'etc/nsswitch.conf'
        p.write_text(content)
        if library:
            lib = root / 'usr/lib/aarch64-linux-gnu/libnss_myhostname.so.2'
            lib.parent.mkdir(parents=True)
            lib.touch()
        return p

    def test_order_other_databases_and_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = self.setup_root(root, 'passwd: files systemd\nhosts: files dns #myhostname\n')
            patcher.patch(root)
            first = p.read_text()
            self.assertIn('hosts:          files myhostname dns', first)
            self.assertIn('passwd: files systemd\n', first)
            patcher.patch(root)
            self.assertEqual(first, p.read_text())

    def test_missing_library_fails_without_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = self.setup_root(root, 'hosts: files dns\n', library=False)
            with self.assertRaises(RuntimeError): patcher.patch(root)
            self.assertEqual(p.read_text(), 'hosts: files dns\n')

    def test_unfamiliar_policy_fails_without_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = 'hosts: files [NOTFOUND=return] dns\n'
            p = self.setup_root(root, original)
            with self.assertRaises(RuntimeError): patcher.patch(root)
            self.assertEqual(p.read_text(), original)

if __name__ == '__main__': unittest.main()
