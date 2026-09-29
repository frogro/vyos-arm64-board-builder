#!/usr/bin/env python3
"""Regression for private receiver state becoming root-owned after ISO updates."""
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('patcher', ROOT / 'tools/patch-vyos-system-image-dtb.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
ns = {'Path': Path}
exec(p.METADATA_HELPER, ns)
restore = ns['_restore_board_config_metadata']

class ConfigMetadataTest(unittest.TestCase):
    @unittest.skipUnless(os.geteuid() == 0, 'Run with sudo to verify real UID/GID preservation')
    def test_private_state_ownership_modes_contents_and_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            src, dst = base/'config', base/'copy'
            private = src/'receiver/state/.config/pulse'
            private.mkdir(parents=True)
            private.chmod(0o2700)
            key = private/'private-state'
            key.write_bytes(b'pairing-state-preserved')
            key.chmod(0o600)
            os.chown(private, 1000, 1001)
            os.chown(key, 1000, 1001)
            # Setgid must survive the chown too.
            private.chmod(0o2700)
            outside = base/'outside'
            outside.write_text('untouched')
            before = outside.stat()
            (private/'external').symlink_to(outside)
            os.lchown(private/'external', 1000, 1001)
            shutil.copytree(src, dst, symlinks=True)
            self.assertEqual((dst/'receiver/state/.config/pulse').stat().st_uid, 0)
            restore(src, dst)
            for relative in ['receiver/state/.config/pulse', 'receiver/state/.config/pulse/private-state', 'receiver/state/.config/pulse/external']:
                a,b = (src/relative).lstat(), (dst/relative).lstat()
                self.assertEqual((a.st_uid,a.st_gid,a.st_mode), (b.st_uid,b.st_gid,b.st_mode))
            self.assertEqual((dst/'receiver/state/.config/pulse/private-state').read_bytes(), key.read_bytes())
            self.assertEqual((outside.stat().st_uid,outside.stat().st_gid,outside.stat().st_mode), (before.st_uid,before.st_gid,before.st_mode))
            self.assertEqual(outside.read_text(), 'untouched')

    def test_reject_destination_symlink_instead_of_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base/'src').mkdir()
            (base/'outside').mkdir()
            (base/'dst').symlink_to(base/'outside', target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, 'type mismatch'):
                restore(base/'src', base/'dst')

    def test_patch_and_dtb_refresh_are_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root/p.TARGET_REL
            target.parent.mkdir(parents=True)
            target.write_text(p.ADD_IMAGE_ANCHOR + "image_name):\n    if True:\n" + p.ROOT_DIR_ANCHOR + "\n        if True:\n            if True:\n" + p.CONFIG_COPY_ANCHOR + '\n')
            self.assertTrue(p.patch_image_installer(root))
            self.assertTrue(p.patch_config_metadata(root))
            before = target.read_text()
            self.assertFalse(p.patch_image_installer(root))
            self.assertFalse(p.patch_config_metadata(root))
            self.assertEqual(target.read_text(), before)
            self.assertEqual(before.count(p.METADATA_CALL), 1)

    def test_changed_upstream_copy_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/p.TARGET_REL
            target.parent.mkdir(parents=True)
            target.write_text('# new upstream copy mechanism\n')
            with self.assertRaises(SystemExit):
                p.patch_config_metadata(Path(tmp))

if __name__ == '__main__':
    unittest.main()
