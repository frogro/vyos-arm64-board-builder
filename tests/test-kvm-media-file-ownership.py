#!/usr/bin/env python3
"""Exercise actual artifact-install stage with foreign ownership, offline."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(os.geteuid()==0, 'needs root to create foreign-owned fixture')
class Ownership(unittest.TestCase):
    def test_existing_soname_links_do_not_redirect_regular_file_copies(self):
        with tempfile.TemporaryDirectory(prefix='vyarm-media-alias-') as tmp:
            w=Path(tmp); a=w/'artifacts'; root=w/'root'
            (a/'bin').mkdir(parents=True);(a/'lib').mkdir();root.mkdir()
            (a/'components.txt').write_text('libmpp|required\n')
            (a/'build.env').write_text('TEST_FIXTURE=yes\n')
            for name in ['mpp_info_test','mpi_enc_test']:
                (a/'bin'/name).write_text('not executed\n')
            names=['librockchip_mpp.so','librockchip_mpp.so.0','librockchip_mpp.so.1']
            for name in names:
                p=a/'lib'/name;p.write_bytes(b'same payload');os.chown(p,12345,12346)
            (a/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(a))+'\n' for p in a.rglob('*') if p.is_file()))
            dest=root/'usr/local/lib/vyos-kvm-media';dest.mkdir(parents=True)
            (dest/names[1]).write_bytes(b'old')
            (dest/names[0]).symlink_to(names[1]);(dest/names[2]).symlink_to(names[1])
            script=(ROOT/'tools/install-kvm-media-stack.sh').read_text().split('command -v chroot',1)[0]
            runner=w/'install-stage.sh';runner.write_text(script)
            subprocess.run(['bash',str(runner),str(root),str(a)],check=True,stdout=subprocess.DEVNULL)
            for name in names:
                p=dest/name;self.assertFalse(p.is_symlink())
                st=p.stat();self.assertEqual((st.st_uid,st.st_gid),(0,0))
                self.assertEqual(p.read_bytes(),b'same payload')

    def test_foreign_uid_and_existing_library_are_normalized(self):
        with tempfile.TemporaryDirectory(prefix='vyarm-media-owner-') as tmp:
            w=Path(tmp); a=w/'artifacts'; root=w/'root'
            (a/'bin').mkdir(parents=True);(a/'lib').mkdir();root.mkdir()
            (a/'components.txt').write_text('libmpp|required\n')
            (a/'build.env').write_text('TEST_FIXTURE=yes\n')
            for name in ['mpp_info_test','mpi_enc_test']:
                (a/'bin'/name).write_text('not executed: artifact copy fixture\n')
            lib=a/'lib/librockchip_mpp.so.0';lib.write_bytes(b'unchanged library payload')
            os.chown(lib,12345,12346)
            link=a/'lib/librockchip_mpp.so';link.symlink_to(lib.name)
            os.chown(link,12345,12346,follow_symlinks=False)
            (a/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(a))+'\n' for p in a.rglob('*') if p.is_file()))
            dest=root/'usr/local/lib/vyos-kvm-media';dest.mkdir(parents=True)
            old=dest/lib.name;old.write_bytes(b'old');os.chown(old,23456,23457)
            # Runtime probes require a complete target rootfs. This test runs
            # the unmodified real installation stage preceding those probes.
            script=(ROOT/'tools/install-kvm-media-stack.sh').read_text().split('command -v chroot',1)[0]
            runner=w/'install-stage.sh';runner.write_text(script)
            subprocess.run(['bash',str(runner),str(root),str(a)],check=True,stdout=subprocess.DEVNULL)
            for name in [lib.name,link.name]:
                s=(dest/name).lstat();self.assertEqual((s.st_uid,s.st_gid),(0,0))
            self.assertEqual(old.read_bytes(),lib.read_bytes())
            self.assertEqual((dest/link.name).readlink(),Path(lib.name))
            self.assertEqual((lib.stat().st_uid,lib.stat().st_gid),(12345,12346))

if __name__=='__main__': unittest.main()
