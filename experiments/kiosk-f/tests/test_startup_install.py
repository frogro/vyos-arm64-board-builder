import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('installer', Path(__file__).resolve().parents[1] / 'install-startup.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class StartupInstall(unittest.TestCase):
    def test_selected_container_and_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installer.install(root, 'lobby-screen')
            installer.install(root, 'lobby-screen')
            drop = root / 'etc/systemd/system/vyos-container-lobby-screen.service.d/kiosk-retry.conf'
            self.assertIn('vyos-kiosk-wait-addresses lobby-screen\n', drop.read_text())
            self.assertNotIn('kiosk-test', drop.read_text())
            self.assertEqual((root / 'usr/local/libexec/vyos-kiosk-wait-addresses').stat().st_mode & 0o777, 0o755)
            self.assertFalse((root / 'config').exists())

    def test_invalid_names_do_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('../other', 'foo\nExecStart=/bin/true', '', 'foo bar', '-bad'):
                with self.assertRaises(ValueError):
                    installer.install(tmp, name)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_symlink_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            (Path(tmp) / 'usr').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                installer.install(tmp, 'screen')
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_custom_dropin_is_preserved_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drop = root / 'etc/systemd/system/vyos-container-screen.service.d/kiosk-retry.conf'
            drop.parent.mkdir(parents=True)
            drop.write_text('# administrator custom settings\n')
            with self.assertRaises(ValueError):
                installer.install(root, 'screen')
            self.assertFalse((root / 'usr').exists())
            self.assertEqual(drop.read_text(), '# administrator custom settings\n')


if __name__ == '__main__':
    unittest.main()
