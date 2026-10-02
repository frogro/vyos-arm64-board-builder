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
        template = root / "usr/share/vyos/templates/login/nsswitch.conf.j2"
        template.parent.mkdir(parents=True)
        template.write_text("passwd: files {{ extra }}\nhosts: files dns #myhostname\n")
        boot = root / 'usr/libexec/vyos/init/vyos-router'
        boot.parent.mkdir(parents=True)
        boot.write_text('security_reset() {\ncat <<EOF >/etc/nsswitch.conf\nhosts: files dns #myhostname\nEOF\n}\n')
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

    def test_regeneration_preserves_fix_with_already_patched_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = self.setup_root(root, 'hosts: files myhostname dns\n')
            template = root / 'usr/share/vyos/templates/login/nsswitch.conf.j2'
            patcher.patch(root)
            self.assertIn('hosts:          files myhostname dns', template.read_text())
            self.assertIn('{{ extra }}', template.read_text())
            boot = root / 'usr/libexec/vyos/init/vyos-router'
            boot_hosts = next(line for line in boot.read_text().splitlines() if line.startswith('hosts:'))
            p.write_text(boot_hosts + '\n')
            self.assertIn('files myhostname dns', p.read_text())
            # Simulate VyOS rendering the template during login configuration.
            p.write_text(template.read_text().replace('{{ extra }}', 'systemd'))
            self.assertIn('files myhostname dns', p.read_text())
            first = template.read_text()
            patcher.patch(root)
            self.assertEqual(first, template.read_text())

    def test_invalid_template_does_not_partially_patch_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = self.setup_root(root, 'hosts: files dns\n')
            template = root / 'usr/share/vyos/templates/login/nsswitch.conf.j2'
            template.write_text('hosts: files [NOTFOUND=return] dns\n')
            with self.assertRaises(RuntimeError): patcher.patch(root)
            self.assertEqual(p.read_text(), 'hosts: files dns\n')

    def test_invalid_boot_writer_does_not_partially_patch_other_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = self.setup_root(root, 'hosts: files dns\n')
            template = root / 'usr/share/vyos/templates/login/nsswitch.conf.j2'
            original_template = template.read_text()
            boot = root / 'usr/libexec/vyos/init/vyos-router'
            boot.write_text('hosts: files [NOTFOUND=return] dns\n')
            with self.assertRaises(RuntimeError): patcher.patch(root)
            self.assertEqual(runtime.read_text(), 'hosts: files dns\n')
            self.assertEqual(template.read_text(), original_template)

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
