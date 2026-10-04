import sys,types,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapter'))
import youtube_web as y
class YouTubeWeb(unittest.TestCase):
 def test_domains(self):
  for url in ['https://www.youtube.com/watch?v=abc','https://youtu.be/abc','https://www.youtube-nocookie.com/embed/abc']:
   self.assertTrue(y.is_youtube(url))
  for url in ['https://youtube.com.evil.example/video','https://evil.example/youtube.com','file://youtube.com/abc']:
   self.assertFalse(y.is_youtube(url))
 def test_api_download_path_is_bypassed(self):
  class Current:
   def prepare_asset(self,data,*args,**kw):return data
  class Legacy:
   def prepare_asset(self,data,*args,**kw):return data
  mix=types.ModuleType('anthias_server.api.serializers.mixins');mix.CreateAssetSerializerMixin=Current
  old=types.ModuleType('anthias_server.api.serializers.v1_1');old.CreateAssetSerializerV1_1=Legacy
  settings=types.ModuleType('anthias_server.settings');settings.settings={'default_duration':10}
  with patch.dict(sys.modules,{mix.__name__:mix,old.__name__:old,settings.__name__:settings}):
   y.install();y.install()
   for cls in (Current,Legacy):
    item=cls();value=item.prepare_asset({'uri':'https://youtube.com/embed/abc','mimetype':'youtube_asset','duration':0})
    self.assertEqual(value['mimetype'],'webpage');self.assertEqual(value['duration'],10)
    self.assertIsNone(item._pending_youtube_uri);self.assertIsNone(item._pending_remote_video_uri)
    uploaded={'uri':'/data/upload.mp4','mimetype':'video','duration':0}
    self.assertEqual(item.prepare_asset(uploaded),uploaded)
