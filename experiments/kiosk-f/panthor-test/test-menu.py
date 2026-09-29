#!/usr/bin/env python3
"""Boot isolation regressions; never read or write the running boot partition."""
import importlib.util
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('menu', Path(__file__).with_name('install-menu.py'))
menu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(menu)
VERSION = '999.202609250800'
RELEASE = '6.18.50-vyos-panthor-cache-test'
TEMPLATE = '''menuentry "999.202609250800" --id existing-normal {
 set boot_opts="boot=live vyos-union=/boot/999.202609250800 console=ttyS2,1500000"
 devicetree "/boot/999.202609250800/dtb/rockchip/rk3588-rock-5b.dtb"
 linux "/boot/999.202609250800/vmlinuz" ${boot_opts}
 initrd "/boot/999.202609250800/initrd.img"
}
'''

class BootMenuTests(unittest.TestCase):
    def test_isolated_payload_keeps_root_and_options(self):
        result = menu.render(TEMPLATE, VERSION, RELEASE)
        self.assertIn('vyos-union=/boot/' + VERSION, result)
        self.assertIn('console=ttyS2,1500000', result)
        for filename in ['Image', 'initrd.img', 'board.dtb']:
            self.assertIn(f'/boot/{VERSION}/panthor-test/{filename}', result)
        self.assertIn('--id vyarm-panthor-', result)
        self.assertNotIn('set default', result)
        self.assertNotIn('save_env', result)
        self.assertNotIn('/vmlinuz"', result)
        self.assertIn('--id existing-normal', TEMPLATE)
        self.assertEqual(result, menu.render(TEMPLATE, VERSION, RELEASE))

    def test_running_image_bind_mount_and_partition_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            persistence = root / 'persistence'
            image = persistence / 'boot' / VERSION
            image.mkdir(parents=True)
            bound = root / 'bound'
            bound.symlink_to(image, target_is_directory=True)
            self.assertEqual(menu.installed_image_dir(VERSION, bound, persistence), bound)
            partition = root / 'partition'
            partition.symlink_to(image.parent, target_is_directory=True)
            self.assertEqual(menu.installed_image_dir(VERSION, partition, persistence), partition / VERSION)
            wrong = root / 'wrong'
            wrong.mkdir()
            with self.assertRaises(ValueError):
                menu.installed_image_dir(VERSION, wrong, persistence)
            with self.assertRaises(ValueError):
                menu.installed_image_dir('../wrong', bound, persistence)

    def test_waits_for_late_shared_grub_mount(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            persistence = root / 'persistence'
            image = persistence / 'boot' / VERSION
            image.mkdir(parents=True)
            grub = persistence / 'boot/grub'
            configs = grub / 'grub.cfg.d/vyos-versions'
            configs.mkdir(parents=True)
            (configs / f'{VERSION}.cfg').write_text(TEMPLATE)
            boot = root / 'boot'
            boot.symlink_to(image)
            with self.assertRaises(TimeoutError):
                menu.wait_for_boot_layout(VERSION, boot, persistence, timeout=0)
            def mount_later(_):
                (image / 'grub').symlink_to(grub)
            with patch.object(menu.time, 'sleep', side_effect=mount_later) as sleep:
                self.assertEqual(menu.wait_for_boot_layout(VERSION, boot, persistence), boot / 'grub/grub.cfg.d')
                sleep.assert_called_once()

    def test_fail_closed_for_changed_templates_and_names(self):
        for template, version, release in [
            (TEMPLATE + TEMPLATE, VERSION, RELEASE),
            (TEMPLATE.replace('devicetree', 'unknown'), VERSION, RELEASE),
            (TEMPLATE, '../../other', RELEASE),
            (TEMPLATE, VERSION, '6.18.50-vyos'),
            (TEMPLATE.replace('linux "', 'linux /'), VERSION, RELEASE),
        ]:
            with self.subTest(version=version, release=release):
                with self.assertRaises(ValueError):
                    menu.render(template, version, release)

if __name__ == '__main__':
    unittest.main()
