#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
s=importlib.util.spec_from_file_location('kernel',Path(__file__).resolve().parents[1]/'tools/ensure-raw-kernel.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Kernel(unittest.TestCase):
    def source(self, root):
        (root/'data/live-build-config/archives').mkdir(parents=True)
        (root/'data/defaults.toml').write_text('kernel_version="6.18.50"\nkernel_flavor="vyos"\nvyos_mirror="https://example.test"\nvyos_branch="rolling"\n')
        (root/'data/live-build-config/archives/vyos-dev.key.chroot').write_text('fixture')
    def test_candidate(self):
        self.assertIsNone(m.candidate(''))
        self.assertIsNone(m.candidate('  Candidate: (none)'))
        self.assertEqual(m.candidate('  Candidate: 6.18.50-1'),'6.18.50-1')
    def test_missing_only_after_successful_index_check(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.source(root)
            with patch.object(m,'run') as run, patch.object(m.subprocess,'check_output',return_value=''):
                self.assertTrue(m.probe(root,root/'packages',root/'result.json'))
                self.assertEqual(run.call_count,1)
                self.assertIn('APT::Update::Error-Mode=any',run.call_args.args)
            with patch.object(m,'run',side_effect=subprocess.CalledProcessError(100,'apt-get')):
                with self.assertRaises(subprocess.CalledProcessError):m.probe(root,root/'packages',root/'result.json')
    def test_package_identity(self):
        with patch.object(m.subprocess,'check_output',side_effect=['Package: linux-image-6.18.50-vyos\nArchitecture: arm64\nVersion: 6.18.50-1\n','-rw-r--r-- root/root 1 today ./boot/vmlinuz-6.18.50-vyos\n']):
            self.assertEqual(m.validate(Path('kernel.deb'),'6.18.50-vyos')['Architecture'],'arm64')
        for name,arch in [('linux-image-6.18.51-vyos','arm64'),('linux-image-6.18.50-vyos','amd64')]:
            with patch.object(m.subprocess,'check_output',return_value=f'Package: {name}\nArchitecture: {arch}\nVersion: 1\n'):
                with self.assertRaises(ValueError):m.validate(Path('kernel.deb'),'6.18.50-vyos')
    def test_checksum_and_source_binding(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.source(root);packages=root/'packages';packages.mkdir()
            (packages/'kernel.deb').write_bytes(b'kernel')
            metadata=root/'kernel.json'
            with patch.object(m.subprocess,'check_output',return_value='abc\n'),patch.object(m,'validate',return_value={}):
                m.record(packages/'kernel.deb','6.18.50-vyos','exact-source-build',root,metadata)
                m.verify_artifact(root,packages,metadata)
                (packages/'kernel.deb').write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'checksum'):m.verify_artifact(root,packages,metadata)
if __name__=='__main__':unittest.main()
