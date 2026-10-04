import importlib.util,json,sys,types,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
schedule=load('schedule','cli/kiosk_schedule.py')
kiosk=load('kiosk_controls','cli/kiosk.py')
remote=load('remote_controls','cli/remote.py')
class Controls(unittest.TestCase):
 def test_native_environment(self):
  v=types.ModuleType('vyos');v.kiosk_schedule=schedule
  with patch.dict(sys.modules,{'vyos':v,'vyos.kiosk_schedule':schedule}):
   env=kiosk.environment({'kiosk':dict(url='https://example.org',display_backend='wayland',audio_muted='enabled',display_schedule=dict(start='08:00',stop='18:00'))})
  self.assertIn('Environment=KIOSK_AUDIO_MUTED="enabled"',env)
  self.assertIn('Environment=KIOSK_DISPLAY_TIMEZONE="UTC"',env)
 def test_reject_older_image_and_x11(self):
  config={'image':'local:test','kiosk':dict(url='https://example.org',display_backend='wayland',audio_muted='enabled')}
  with patch.object(remote.subprocess,'run',return_value=types.SimpleNamespace(stdout=json.dumps([{'Config':{'Labels':{'io.vyarm.kiosk.wayland-drm':'1'}}}]))):
   with self.assertRaisesRegex(ValueError,'display schedule'):remote.verify_image(config)
  config['kiosk']['display_backend']='x11'
  with self.assertRaisesRegex(ValueError,'Wayland'):kiosk.environment(config)
