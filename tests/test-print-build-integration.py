#!/usr/bin/env python3
"""Verify independent E selection and image/update payload boundaries."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
feature=load('features','tools/feature-profile.py')
planner=load('planner','tools/ci/multimedia-plan.py')
stager=load('stage','experiments/profile-e/image/stage-runtime.py')
class PrintBuild(unittest.TestCase):
 def test_all_boards_independent_e_and_g_share_one_usb_selection(self):
  for board in ('rock-5b','orangepi5-plus','raspberry-pi-5','radxa-e52c'):
   p=planner.plan(board,print_server=True)
   self.assertTrue(p['usb_server']);self.assertFalse(p['graphics']);self.assertFalse(p['kvm'])
  self.assertEqual(feature.derive(False,False,False,print_server_e=True)['profile'],'print')
  self.assertEqual(feature.derive(True,False,False,receiver_g=True,print_server_e=True)['profile'],'network-print-receiver')
  self.assertNotIn('print_server_e',feature.derive(True,False,False)['features'])
 def test_stage_verified_archive_and_reject_corruption(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'root';root.mkdir();artifact=Path(tmp)/'artifact';artifact.mkdir()
   archive=b'test-archive';(artifact/'runtime.tar').write_bytes(archive)
   tag='localhost/vyarm-print:e-abc123'
   meta=dict(profile='print-server-e',tag=tag,archive_sha256=hashlib.sha256(archive).hexdigest(),source_commit='test')
   info=[dict(Architecture='arm64',Id='a'*64,RepoTags=[tag],Config=dict(Labels={'io.vyarm.print.version':'1'}))]
   (artifact/'runtime.json').write_text(json.dumps(meta));(artifact/'image.json').write_text(json.dumps(info))
   stager.stage(root,artifact)
   self.assertTrue((root/'etc/systemd/system/vyos.target.wants/vyarm-print-runtime.service').is_symlink())
   self.assertTrue((root/'usr/share/vyos-arm64-board-builder/print-runtime/runtime.json').is_file())
   self.assertFalse((root/'config/profile-e/virtualhere-bin/vhusbdarm64').exists())
   (artifact/'runtime.tar').write_bytes(b'corrupted')
   with self.assertRaisesRegex(ValueError,'checksum'):stager.stage(root,artifact)
 def test_native_print_only_package(self):
  base=load('native_test','tests/test-vyos-1x-profile.py')
  with tempfile.TemporaryDirectory() as tmp:
   root=base.Tests().source(tmp)
   metadata=base.m.prepare(root,'999.0-14891-gd185906f3',False,print_server=True)
   self.assertEqual(metadata['profiles'],['print-server-e'])
   self.assertTrue((root/'src/conf_mode/service_usb_server.py').is_file())
   self.assertFalse((root/'src/conf_mode/service_kvm_over_ip.py').exists())
   self.assertFalse((root/'python/vyos/receiver.py').exists())
if __name__=='__main__':unittest.main()
