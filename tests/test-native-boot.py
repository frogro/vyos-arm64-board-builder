#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid5, NAMESPACE_URL

ROOT = Path(__file__).resolve().parents[1]

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

boot = load(ROOT / 'tools/firmware-providers/armbian-uboot/board_boot.py', 'board_boot_test')
installer = load(ROOT / 'tools/install-native-boot.py', 'install_native_test')
update = load(ROOT / 'tools/patch-vyos-system-image-dtb.py', 'dtb_update_test')

class NativeBootTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'root'; self.fat = Path(self.temp.name) / 'fat'
        self.fat.mkdir(); (self.root / boot.VERSIONS).mkdir(parents=True)
        self.metadata = dict(schema=1, board='example-board', architecture='arm64',
            firmware_provider='armbian-uboot', update_provider='uboot-extlinux',
            profile='network', device_tree='vendor/board.dtb', console='ttyS2', baud=1500000,
            firmware_partition=2)
        self.add('old'); self.default('old')

    def add(self, version, content=''):
        d = self.root / 'boot' / version
        (d / 'dtb/vendor').mkdir(parents=True)
        for filename in ('vmlinuz', 'initrd.img', 'dtb/vendor/board.dtb'):
            (d / filename).write_text(filename + content)
        (d / 'board-boot.json').write_text(json.dumps(self.metadata))
        (self.root / boot.VERSIONS / (version + '.cfg')).write_text(
            f'    set boot_opts="boot=live rootdelay=5 vyos-union=/boot/{version} quiet"\n')

    def default(self, version):
        (self.root / boot.DEFAULTS).write_text(f'set default="{uuid5(NAMESPACE_URL, version)}"\n'
            'set console_type="ttyS"\nset console_num="2"\nset console_speed="1500000"\n')

    def sync(self):boot.sync(self.root, self.fat, self.metadata)
    def menu(self):return (self.fat / 'extlinux/extlinux.conf').read_text()

    def test_interrupt_dtb_gate(self):
        import shutil, subprocess
        if not shutil.which('dtc') or not shutil.which('fdtget'):
            self.skipTest('device-tree-compiler is needed for DTB fixture integration')
        source = Path(self.temp.name) / 'interrupts.dts'
        target = source.with_suffix('.dtb'); report = source.with_suffix('.json')
        for prop, expected in [('dma-noncoherent;', 0), ('', 1)]:
            source.write_text('/dts-v1/; / { compatible="rockchip,rk3582"; gic { compatible="arm,gic-v3"; ' + prop + ' its { compatible="arm,gic-v3-its"; ' + prop + ' }; }; };')
            subprocess.run(['dtc','-I','dts','-O','dtb','-o',str(target),str(source)],check=True,capture_output=True)
            result = subprocess.run(['python3',str(ROOT/'tools/audit-interrupt-dtb.py'),str(target),str(report)],capture_output=True)
            self.assertEqual(result.returncode, expected)

    def test_initial_boot_identity_and_serial(self):
        self.sync(); menu = self.menu()
        self.assertIn('BOOT_IMAGE=/boot/old/vmlinuz', menu)
        self.assertIn('vyos-union=/boot/old', menu)
        self.assertIn('console=ttyS2,1500000n8', menu)
        self.assertEqual(menu, (self.fat / 'boot/extlinux/extlinux.conf').read_text())
        for line in menu.splitlines():
            if line.strip().startswith(('LINUX ', 'INITRD ', 'FDT ')):
                self.assertTrue((self.fat / line.split()[1].lstrip('/')).is_file())

    def test_add_default_rollback_delete(self):
        self.sync(); self.add('new', 'new payload'); self.sync()
        self.assertIn('VyOS old', self.menu()); self.assertIn('VyOS new', self.menu())
        self.assertTrue(self.menu().startswith('DEFAULT vyos-' + uuid5(NAMESPACE_URL, 'old').hex))
        self.default('new'); self.sync()
        self.assertTrue(self.menu().startswith('DEFAULT vyos-' + uuid5(NAMESPACE_URL, 'new').hex))
        self.default('old'); self.sync()
        (self.root / boot.VERSIONS / 'new.cfg').unlink(); self.sync()
        self.assertNotIn('VyOS new', self.menu())
        self.assertEqual(len(list((self.fat / 'vyos-boot/payloads').iterdir())), 1)

    def test_identical_payloads_are_shared_for_custom_image_names(self):
        self.add('custom-name'); self.sync()
        self.assertEqual(len(list((self.fat / 'vyos-boot/payloads').iterdir())), 1)
        self.assertIn('BOOT_IMAGE=/boot/custom-name/vmlinuz', self.menu())

    def test_missing_payload_preserves_old_menu(self):
        self.sync(); previous = self.menu(); self.add('new', 'new')
        (self.root / 'boot/new/initrd.img').unlink()
        with self.assertRaises(RuntimeError): self.sync()
        self.assertEqual(self.menu(), previous)

    def test_missing_default_preserves_menu(self):
        self.sync(); previous = self.menu(); self.default('missing')
        with self.assertRaises(RuntimeError): self.sync()
        self.assertEqual(self.menu(), previous)

    def test_full_boot_partition_preserves_menu(self):
        self.sync(); previous = self.menu(); self.add('new', 'new')
        from collections import namedtuple
        usage = namedtuple('Usage', 'total used free')(100, 100, 0)
        with patch.object(boot.shutil, 'disk_usage', return_value=usage):
            with self.assertRaises(RuntimeError): self.sync()
        self.assertEqual(self.menu(), previous)

    def test_second_menu_write_failure_restores_both(self):
        self.sync(); previous = self.menu(); self.add('new', 'new'); self.default('new')
        original = boot.atomic_write; counter = 0
        def fail_once(path, data):
            nonlocal counter
            counter += 1
            if counter == 2: raise OSError('simulated write failure')
            return original(path, data)
        with patch.object(boot, 'atomic_write', side_effect=fail_once):
            with self.assertRaises(OSError): self.sync()
        self.assertEqual(self.menu(), previous)
        self.assertEqual((self.fat / 'boot/extlinux/extlinux.conf').read_text(), previous)

    def test_provider_profile_and_dtb_mismatches_rejected(self):
        self.sync(); previous = self.menu()
        for field in ('board', 'profile', 'firmware_provider', 'update_provider'):
            altered = dict(self.metadata); altered[field] = 'wrong'
            (self.root / 'boot/old/board-boot.json').write_text(json.dumps(altered))
            with self.assertRaises(RuntimeError): self.sync()
            self.assertEqual(self.menu(), previous)
        for value in ('../x.dtb', '/tmp/x.dtb', 'a//b.dtb', 'a/./b.dtb', 'x\n.dtb'):
            with self.assertRaises(RuntimeError):boot.dtb_path(value)

    def test_update_helper_copies_native_metadata_and_checks_contract(self):
        import shutil
        ns = dict(Path=Path, loads=json.loads, copy=shutil.copy)
        exec(update.HELPER_BLOCK, ns)
        iso = Path(self.temp.name) / 'iso'; (iso / 'live/dtb/vendor').mkdir(parents=True)
        (iso / 'live/dtb/vendor/board.dtb').write_text('new dtb')
        manifest = dict(self.metadata, schema=3)
        (iso / 'board-manifest.json').write_text(json.dumps(manifest))
        (iso / 'live/boot-provider.json').write_text(json.dumps(self.metadata))
        profile = Path(self.temp.name) / 'profile/profile.json'; profile.parent.mkdir()
        profile.write_text(json.dumps(self.metadata))
        profile.with_name('boot-provider.json').write_text(json.dumps(self.metadata))
        helper = ns['_copy_board_dtb_from_update_iso']
        self.assertTrue(helper(iso, self.root, 'new', profile))
        self.assertEqual(json.loads((self.root / 'boot/new/board-boot.json').read_text()), self.metadata)
        for field in ('board', 'profile', 'firmware_provider', 'update_provider', 'device_tree'):
            bad = dict(manifest); bad[field] = 'wrong'
            (iso / 'board-manifest.json').write_text(json.dumps(bad))
            with self.assertRaises(RuntimeError):helper(iso, self.root, 'rejected', profile)
        self.assertFalse((self.root / 'boot/rejected').exists())

    def test_grub_mutation_rolls_back_on_sync_failure(self):
        from contextlib import contextmanager
        import sys, types
        metadata_path = Path(self.temp.name) / 'boot-provider.json'
        metadata_path.write_text(json.dumps(self.metadata))
        original = (self.root / boot.DEFAULTS).read_bytes()
        @contextmanager
        def mount(root, metadata): yield self.fat
        def set_default(version_name, root_dir=''):
            self.default(version_name)
        vyos = types.ModuleType('vyos'); system = types.ModuleType('vyos.system')
        system.disk = types.SimpleNamespace(find_persistence=lambda: str(self.root))
        vyos.system = system
        lockpath = Path(self.temp.name) / 'lock'
        builtin_open = open
        def open_lock(path, *args, **kwargs):
            return builtin_open(lockpath if str(path).startswith('/run/lock/') else path, *args, **kwargs)
        with patch.dict(sys.modules, {'vyos': vyos, 'vyos.system': system}), \
             patch.object(boot, 'PROFILE', metadata_path), \
             patch.object(boot, 'mounted_firmware', mount), \
             patch('builtins.open', side_effect=open_lock):
            self.sync()
            previous_menu = self.menu()
            with self.assertRaises(RuntimeError):
                boot.decorate(set_default)('missing', str(self.root))
            self.assertEqual((self.root / boot.DEFAULTS).read_bytes(), original)
            self.assertEqual(self.menu(), previous_menu)

    def test_console_patch_changes_only_speed_node(self):
        console = load(ROOT / 'tools/patch-board-console.py', 'console_test')
        node = dict(name='speed', data=dict(constraints=[['regex',console.OLD]],
            completion_help=[['list','115200']], value_help=[]), children=[])
        for label in ('device','console','system',''):
            node = dict(name=label,data={},children=[node])
        cache = self.root / 'usr/share/vyos/reftree.cache';cache.parent.mkdir(parents=True)
        cache.write_text(json.dumps(node))
        cli = self.root / 'opt/vyatta/share/vyatta-cfg/templates/system/console/device/node.tag/speed/node.def'
        cli.parent.mkdir(parents=True);cli.write_text('syntax: '+console.OLD+'\n')
        console.patch(self.root);first=cache.read_text();console.patch(self.root)
        self.assertEqual(first,cache.read_text());self.assertIn(console.NEW,cli.read_text())
        self.assertNotIn('default_value',cache.read_text())

    def test_patcher_is_guarded_and_idempotent(self):
        path = Path(self.temp.name) / 'grub.py'
        path.write_text('\n'.join(f'def {name}(*args, **kwargs): pass' for name in (
            'version_add','version_del','set_default','set_console_type','set_serial_console')))
        installer.patch_grub(path); first = path.read_text(); installer.patch_grub(path)
        self.assertEqual(first, path.read_text())
        path.write_text('def changed_api(): pass\n')
        with self.assertRaises(RuntimeError):installer.patch_grub(path)

if __name__ == '__main__':unittest.main()
