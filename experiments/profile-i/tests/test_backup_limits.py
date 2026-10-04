import io,sys,tarfile,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapter'))
import backup_limits
class BackupLimits(unittest.TestCase):
 def test_rejects_expanded_size_before_restore(self):
  with tempfile.TemporaryDirectory() as d:
   archive=Path(d)/'backup.tar.gz'
   with tarfile.open(archive,'w:gz') as tar:
    member=tarfile.TarInfo('anthias_assets/example');member.size=100
    tar.addfile(member,io.BytesIO(b'x'*100))
   calls=[]
   helper=types.SimpleNamespace(recover=lambda p:calls.append(p),_safe_tar_member=lambda m,r:True,BackupRecoverError=ValueError)
   lib=types.ModuleType('anthias_server.lib');lib.backup_helper=helper
   with patch.dict(sys.modules,{'anthias_server':types.ModuleType('anthias_server'),'anthias_server.lib':lib}),patch.dict('os.environ',{'HOME':d,'I_STORAGE_LIMIT_BYTES':'50','I_FREE_RESERVE_BYTES':'0'}):
    backup_limits.install()
    with self.assertRaisesRegex(ValueError,'Expanded backup'):helper.recover(str(archive))
   self.assertEqual(calls,[])
 def test_valid_archive_delegates_once(self):
  with tempfile.TemporaryDirectory() as d:
   archive=Path(d)/'backup.tar.gz'
   with tarfile.open(archive,'w:gz') as tar:
    member=tarfile.TarInfo('anthias_assets/example');member.size=3
    tar.addfile(member,io.BytesIO(b'abc'))
   calls=[]
   helper=types.SimpleNamespace(recover=lambda p:calls.append(p),_safe_tar_member=lambda m,r:True,BackupRecoverError=ValueError)
   lib=types.ModuleType('anthias_server.lib');lib.backup_helper=helper
   with patch.dict(sys.modules,{'anthias_server':types.ModuleType('anthias_server'),'anthias_server.lib':lib}),patch.dict('os.environ',{'HOME':d,'I_STORAGE_LIMIT_BYTES':'10000','I_FREE_RESERVE_BYTES':'0'}):
    backup_limits.install();backup_limits.install();helper.recover(str(archive))
   self.assertEqual(calls,[str(archive)])
