#!/usr/bin/env python3
"""Exercise generated firmware aliases without downloading firmware."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('stage', Path(__file__).resolve().parents[1] / 'tools/stage-network-firmware.py')
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)

class FirmwareAliases(unittest.TestCase):
    def test_selected_alias_materializes_target_outside_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, dest = Path(tmp) / 'source', Path(tmp) / 'out'
            (source / 'rtl_bt').mkdir(parents=True)
            (source / 'rtl_bt/rtl8761bu_config.bin').write_bytes(b'config')
            (source / 'WHENCE').write_text('Link: rtl_bt/rtl8852bu_config.bin -> rtl8761bu_config.bin\nLink: rtl_bt/chain.bin -> rtl8852bu_config.bin\n')
            self.assertEqual(stage.copy_pattern(source, dest, 'rtl_bt/rtl8852bu*'), ['rtl_bt/rtl8852bu_config.bin'])
            self.assertEqual((dest / 'rtl_bt/rtl8852bu_config.bin').read_bytes(), b'config')
            self.assertFalse((dest / 'rtl_bt/rtl8761bu_config.bin').exists())
            self.assertEqual(stage.copy_pattern(source, dest, 'rtl_bt/chain.bin'), ['rtl_bt/chain.bin'])

    def test_bad_aliases_fail(self):
        for declaration in ['Link: a -> b\nLink: b -> a\n', 'Link: a -> ../escape\n']:
            with self.subTest(declaration=declaration), tempfile.TemporaryDirectory() as tmp:
                source = Path(tmp)
                (source / 'WHENCE').write_text(declaration)
                with self.assertRaises(RuntimeError):
                    stage.copy_pattern(source, source / 'out', 'a')

if __name__ == '__main__':
    unittest.main()
