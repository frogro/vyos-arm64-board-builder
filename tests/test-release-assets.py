import hashlib, json
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
spec=importlib.util.spec_from_file_location('publisher',Path(__file__).resolve().parents[1]/'tools/publish-release-assets.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ReleaseAssets(unittest.TestCase):
 def test_split_boundary_and_reassembly(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp);p=d/'test.img.xz';p.write_bytes(bytes(range(100)))
   parts=m.split_image(p,d,limit=100,chunk=40)
   self.assertEqual([x.stat().st_size for x in parts],[40,40,20])
   self.assertEqual(b''.join(x.read_bytes() for x in parts),p.read_bytes())
   self.assertEqual(m.split_image(p,d,limit=101,chunk=40),[p])
 def test_iso_is_not_silently_split(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp);p=d/'test.iso';p.write_bytes(b'1234')
   with self.assertRaises(ValueError):m.split_image(p,d,limit=4,chunk=2)
 def test_draft_without_git_tag_is_verified_before_publication(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp);a=d/'image.iso';a.write_bytes(b'iso');n=d/'notes';n.write_text('notes')
   def output(args, **kwargs):
    if 'api' in args:
     self.assertIn('--slurp',args)
     self.assertNotIn('/tags/', ' '.join(args))
     return json.dumps([[{'tag_name':'tag','assets':[{'name':a.name,'state':'uploaded','digest':'sha256:'+hashlib.sha256(b'iso').hexdigest()}]}]])
    return ''
   def run(args, **kwargs):
    return SimpleNamespace(returncode=1 if 'view' in args else 0)
   with patch.object(m.subprocess,'run',side_effect=run), patch.object(m.subprocess,'check_output',side_effect=output) as gh:
    m.publish('owner/repo','tag','a'*40,'title',n,[a])
    self.assertTrue(any('--draft=false' in c.args[0] for c in gh.call_args_list))
 def test_failed_upload_never_publishes_draft(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp);a=d/'image.iso';a.write_bytes(b'iso');n=d/'notes';n.write_text('notes')
   with patch.object(m.subprocess,'run',return_value=SimpleNamespace(returncode=1)) as run, patch.object(m.subprocess,'check_output',return_value='') as gh, patch.object(m.time,'sleep'):
    with self.assertRaises(RuntimeError):m.publish('owner/repo','tag','a'*40,'title',n,[a])
    self.assertFalse(any('--draft=false' in c.args[0] for c in gh.call_args_list))
    self.assertEqual(sum('upload' in c.args[0] for c in run.call_args_list),4)
if __name__=='__main__':unittest.main()
