#!/usr/bin/env python3
"""Exercise Pi update handoff without claiming physical firmware validation."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import sys
import types
import unittest
from unittest.mock import patch
from uuid import uuid5, NAMESPACE_URL

ROOT = Path(__file__).resolve().parents[1]
def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module
common = load(ROOT / 'tools/firmware-providers/armbian-uboot/board_boot.py')
rpi = load(ROOT / 'tools/firmware-providers/raspberrypi-native/board_boot_rpi.py')
update = load(ROOT / 'tools/patch-vyos-system-image-dtb.py')

class PiBootTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'root'; self.fat = Path(self.temp.name) / 'fat'
        self.fat.mkdir(); (self.root / common.VERSIONS).mkdir(parents=True)
        (self.fat / 'config.txt').write_text('[all]\narm_64bit=1\ndtoverlay=bcm2712d0\n')
        self.meta = dict(schema=1, board='raspberry-pi-5', architecture='arm64', profile='network',
            firmware_provider='raspberrypi-native', update_provider='firmware-files',
            firmware_partition=1, device_tree='broadcom/bcm2712-rpi-5-b.dtb',
            console='ttyAMA10', baud=115200, display_console=True)
        self.add('old'); self.select('old'); self.sync()
    def add(self, name):
        d = self.root / 'boot' / name
        for filename in ('vmlinuz', 'initrd.img', 'dtb/' + self.meta['device_tree'], 'rpi/bcm2712d0.dtbo'):
            p = d / filename; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(name + filename)
        (d / 'board-boot.json').write_text(json.dumps(self.meta))
        (self.root / common.VERSIONS / (name + '.cfg')).write_text(f'set boot_opts="boot=live vyos-union=/boot/{name}"\n')
    def select(self, name):
        (self.root / common.DEFAULTS).write_text(f'set default="uuid5-{uuid5(NAMESPACE_URL, name)}"\n')
    def sync(self):rpi.sync(self.root, self.fat, self.meta, common)
    def config(self):return (self.fat / 'config.txt').read_text()
    def bundle(self):return self.fat / next(l.split('=',1)[1] for l in self.config().splitlines() if l.startswith('os_prefix='))
    def test_runtime_dispatch_and_grub_rollback(self):
        from contextlib import contextmanager
        vyos = types.ModuleType('vyos'); system = types.ModuleType('vyos.system')
        system.board_boot_rpi = rpi
        system.disk = types.SimpleNamespace(find_persistence=lambda: str(self.root))
        vyos.system = system
        profile = Path(self.temp.name) / 'runtime-provider.json'
        profile.write_text(json.dumps(self.meta))
        @contextmanager
        def mounted(root, metadata):yield self.fat
        def select(version_name, root_dir=''):self.select(version_name)
        before = (self.root / common.DEFAULTS).read_bytes()
        with patch.dict(sys.modules, {'vyos':vyos, 'vyos.system':system}), \
             patch.object(common, 'PROFILE', profile), \
             patch.object(common, 'mounted_firmware', mounted):
            common.sync(self.root, self.fat, self.meta)
            # Use a temporary lock file; no privileged /run write in CI.
            original_open = open
            def redirect(path, *args, **kwargs):
                if path == '/run/lock/vyos-native-boot.lock':path = Path(self.temp.name) / 'lock'
                return original_open(path, *args, **kwargs)
            with patch('builtins.open', side_effect=redirect):
                with self.assertRaises(RuntimeError):common.decorate(select)('missing', self.root)
        self.assertEqual((self.root / common.DEFAULTS).read_bytes(), before)

    def test_add_select_rollback_and_delete(self):
        old = self.bundle(); self.add('new'); self.sync(); self.assertEqual(self.bundle(), old)
        self.select('new'); self.sync(); new = self.bundle()
        self.assertNotEqual(old, new); self.assertEqual((new / 'vmlinuz').read_text(), 'newvmlinuz')
        self.assertIn('BOOT_IMAGE=/boot/new/vmlinuz', (new / 'cmdline.txt').read_text())
        self.assertIn('console=ttyAMA10,115200n8', (new / 'cmdline.txt').read_text())
        self.select('old'); self.sync(); self.assertEqual(self.bundle(), old)
        (self.root / common.VERSIONS / 'new.cfg').unlink(); self.sync()
        self.assertEqual(self.bundle(), old); self.assertTrue(new.exists())
        self.assertEqual(self.config().count('dtoverlay=bcm2712d0'), 1)
    def test_missing_payload_default_and_wrong_profile_preserve_selection(self):
        previous = self.config(); self.select('absent')
        with self.assertRaises(RuntimeError):self.sync()
        self.add('new'); self.select('new'); (self.root / 'boot/new/initrd.img').unlink()
        with self.assertRaises(RuntimeError):self.sync()
        self.assertEqual(self.config(), previous)
        self.select('old'); p = self.root / 'boot/old/board-boot.json'
        p.write_text(json.dumps(dict(self.meta, profile='wrong')))
        with self.assertRaises(RuntimeError):self.sync()
        self.assertEqual(self.config(), previous)
    def test_full_fat_preserves_selection(self):
        previous = self.config(); self.add('new'); self.select('new')
        with patch.object(rpi.shutil, 'disk_usage', return_value=type('Usage', (), {'free':0})()):
            with self.assertRaises(RuntimeError):self.sync()
        self.assertEqual(self.config(), previous)
    def test_publication_failure_restores_config(self):
        previous = self.config(); self.add('new'); self.select('new')
        original = common.atomic_write; failed = False
        def fail(path, data):
            nonlocal failed
            original(path, data)
            if Path(path) == self.fat / 'config.txt' and not failed:
                failed = True; raise OSError('simulated failure after replacement')
        with patch.object(common, 'atomic_write', side_effect=fail):
            with self.assertRaises(OSError):self.sync()
        self.assertEqual(self.config(), previous)
    def test_corrupt_cache_rejected(self):
        (self.bundle() / 'vmlinuz').write_text('corrupt')
        with self.assertRaises(RuntimeError):self.sync()
    def test_iso_import_requires_overlay_and_copies_it(self):
        ns = dict(Path=Path, loads=json.loads, copy=shutil.copy); exec(update.HELPER_BLOCK, ns)
        iso = Path(self.temp.name) / 'iso'
        p = iso / 'live/dtb' / self.meta['device_tree']; p.parent.mkdir(parents=True); p.write_text('dtb')
        (iso / 'board-manifest.json').write_text(json.dumps(dict(self.meta, schema=3)))
        (iso / 'live/boot-provider.json').write_text(json.dumps(self.meta))
        profile = Path(self.temp.name) / 'profile.json'; profile.write_text(json.dumps(self.meta))
        profile.with_name('boot-provider.json').write_text(json.dumps(self.meta))
        helper = ns['_copy_board_dtb_from_update_iso']
        with self.assertRaises(RuntimeError):helper(iso, self.root, 'import', profile)
        p = iso / 'live/rpi/bcm2712d0.dtbo'; p.parent.mkdir(); p.write_text('overlay')
        helper(iso, self.root, 'import', profile)
        self.assertEqual((self.root / 'boot/import/rpi/bcm2712d0.dtbo').read_text(), 'overlay')
        self.assertEqual(json.loads((self.root / 'boot/import/board-boot.json').read_text()), self.meta)

if __name__ == '__main__':unittest.main()
