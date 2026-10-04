import io,json,sys,tarfile,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapter'))
import backup_settings as b
class SettingsBackup(unittest.TestCase):
 def test_roundtrip_and_scoped_fields(self):
  settings=dict(rotation='90',output='auto',muted=True,schedule=dict(start='08:00',stop='19:00',days='mon,fri',timezone='Europe/Berlin'))
  blob=io.BytesIO()
  with patch.object(b,'host_request',return_value=settings):
   with tarfile.open(fileobj=blob,mode='w:gz') as t:b.add_settings(t)
  blob.seek(0)
  with tarfile.open(fileobj=blob,mode='r:gz') as t:self.assertEqual(b.read_settings(t),settings)
  with self.assertRaises(ValueError):b.validate(dict(settings,commands='delete interfaces'))
 def test_old_archive_and_duplicate_rejection(self):
  for duplicate in (False,True):
   blob=io.BytesIO()
   with tarfile.open(fileobj=blob,mode='w') as t:
    if duplicate:
     for _ in range(2):t.addfile(tarfile.TarInfo(b.MEMBER))
   blob.seek(0)
   with tarfile.open(fileobj=blob) as t:
    if duplicate:
     with self.assertRaises(ValueError):b.read_settings(t)
    else:self.assertIsNone(b.read_settings(t))
 def test_invalid_values(self):
  good=dict(rotation='0',output='auto',muted=False,schedule=None)
  for changes in ({'rotation':'45'},{'output':'auto; reboot'},{'muted':'false'},{'schedule':{'start':'wrong'}}):
   with self.assertRaises(ValueError):b.validate(dict(good,**changes))
