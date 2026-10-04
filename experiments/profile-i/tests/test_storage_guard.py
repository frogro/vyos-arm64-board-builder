import asyncio,json,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapter'))
from storage_guard import Guard,budget,Rejected,GIB
class StorageTests(unittest.TestCase):
 def test_reject_before_read(self):
  async def test():
   called=[];sent=[]
   async def app(*a):called.append(True)
   async def receive():raise AssertionError('rejected upload body must not be read')
   async def send(m):sent.append(m)
   with tempfile.TemporaryDirectory() as d:
    await Guard(app,d)({'type':'http','method':'POST','headers':[(b'content-type',b'multipart/form-data'),(b'content-length',str(3*GIB).encode())]},receive,send)
   self.assertFalse(called);self.assertEqual(sent[0]['status'],413)
  asyncio.run(test())
 def test_limits(self):
  with tempfile.TemporaryDirectory() as d:
   Path(d,'used').write_bytes(b'x'*80)
   with self.assertRaises(Rejected):budget({'content-length':'30'},d,100,100,0)
   with patch('storage_guard.shutil.disk_usage') as disk:
    disk.return_value.free=5
    with self.assertRaises(Rejected):budget({'content-length':'1'},d,100,100,10)
   with self.assertRaises(Rejected):budget({},d,100,100,0)
   with self.assertRaises(Rejected):budget({'content-length':'2','content-range':'bytes 9-2/10'},d,100,100,0)
 def test_chunk_remaining(self):
  with tempfile.TemporaryDirectory() as d:
   Path(d,'partial').write_bytes(b'x'*80)
   self.assertEqual(budget({'content-length':'10','content-range':'bytes 80-89/100'},d,100,100,0),10)
if __name__=='__main__':unittest.main()
