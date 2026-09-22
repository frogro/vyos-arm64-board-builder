#!/usr/bin/env python3
"""Exercise real selector against isolated evaluated-Armbian fixtures."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class BootPolicy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'tools').mkdir()
        (self.root / 'profiles').mkdir()
        for name in ('tools/select-uboot-branch.sh', 'profiles/boot-branches.conf'):
            shutil.copy2(ROOT / name, self.root / name)
        resolver = self.root / 'tools/resolve-armbian-effective-config.sh'
        resolver.write_text('#!/bin/bash\nset -eu\nmkdir -p "$3"\nprintf "KERNEL_TARGET=%q\\n" "${TEST_TARGETS:-current,vendor,edge}" > "$3/config.env"\n')
        resolver.chmod(0o755)

    def select(self, board, request='auto', hardware='current', targets='current,vendor,edge'):
        return subprocess.run(['bash', str(self.root / 'tools/select-uboot-branch.sh'),
            board, request, hardware], text=True, capture_output=True,
            env={**os.environ, 'TEST_TARGETS': targets})

    def test_e52c_automatic_native_boot(self):
        result = self.select('radxa-e52c')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'vendor')

    def test_other_boards_unchanged(self):
        for board in ('rock-5b', 'raspberry-pi-5', 'unknown'):
            with self.subTest(board=board):
                self.assertEqual(self.select(board).stdout.strip(), 'current')

    def test_explicit_override_preserved(self):
        self.assertEqual(self.select('radxa-e52c', 'current').stdout.strip(), 'current')

    def test_missing_required_branch_fails_closed(self):
        result = self.select('radxa-e52c', targets='current,edge')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('configured boot branch', result.stderr)

    def test_other_hardware_branch_unchanged(self):
        self.assertEqual(self.select('radxa-e52c', hardware='edge').stdout.strip(), 'edge')

if __name__ == '__main__':
    unittest.main()
