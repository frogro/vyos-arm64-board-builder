#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('compat', ROOT/'tools/prepare-rk3588-decoder-patch.py')
compat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compat)
PATCHES = list((ROOT/'profiles/base-hardware/kernel-patches').glob('*/0*-rk3588-v4l2-decoder.patch'))
class Compat(unittest.TestCase):
    def test_both_board_patches(self):
        self.assertEqual(len(PATCHES), 2)
        for path in PATCHES:
            patch = path.read_text()
            self.assertEqual(compat.prepare(patch, None), patch)
            start = patch.index('--- /dev/null\n+++ b/include/media/v4l2-hevc.h\n')
            end = patch.index('\n--- ', start + 1) + 1
            block = patch[start:end]
            # Apply the actual creation hunk to obtain its required file.
            with tempfile.TemporaryDirectory() as directory:
                subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', directory], input=block, text=True, check=True, capture_output=True)
                header = (Path(directory)/compat.HEADER).read_text()
                self.assertEqual(compat.prepare(patch, header), patch[:start]+patch[end:])
                with self.assertRaises(RuntimeError):
                    compat.prepare(patch, header+'/* changed upstream */\n')
                with self.assertRaises(RuntimeError):
                    compat.prepare(patch.replace('+++ b/include/media/v4l2-hevc.h', '+++ b/include/media/changed.h'), header)
if __name__ == '__main__':
    unittest.main()
