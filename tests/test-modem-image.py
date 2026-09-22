#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import tempfile
import unittest
spec = importlib.util.spec_from_file_location('audit', Path(__file__).resolve().parents[1]/'tools/check-modem-image.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ImageAudit(unittest.TestCase):
    def test_missing_payload_and_builtins(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            cfg = root/'kernel.config'
            cfg.write_text(''.join('CONFIG_'+k+'=m\n' for k in m.REQUIRED))
            missing = m.audit(root,cfg)
            self.assertIn('rndis_host.ko', missing)
            self.assertIn('mbimcli', missing)
            for name in m.COMMANDS:
                p=root/'usr/bin'/name
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text('test'); p.chmod(0o755)
            modules=root/'usr/lib/modules/test/kernel'
            modules.mkdir(parents=True)
            for name in m.MODULES.values():
                (modules/(name+'.ko.xz')).write_text('module')
            self.assertEqual(m.audit(root,cfg),[])
            (modules/'rndis_host.ko.xz').unlink()
            cfg.write_text(cfg.read_text().replace('CONFIG_USB_NET_RNDIS_HOST=m','CONFIG_USB_NET_RNDIS_HOST=y'))
            self.assertEqual(m.audit(root,cfg),[])
            cfg.write_text(cfg.read_text().replace('CONFIG_USB_NET_RNDIS_HOST=y','# CONFIG_USB_NET_RNDIS_HOST is not set'))
            self.assertIn('CONFIG_USB_NET_RNDIS_HOST',m.audit(root,cfg))
            (root/'usr/bin/mbimcli').unlink()
            (root/'usr/bin/mbimcli').symlink_to('/bin/sh')
            self.assertIn('mbimcli',m.audit(root,cfg))

if __name__ == '__main__': unittest.main()
