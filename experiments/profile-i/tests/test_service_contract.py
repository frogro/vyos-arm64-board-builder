import importlib.util,sys,types,unittest
from pathlib import Path
from unittest.mock import patch
class ServiceContract(unittest.TestCase):
 def test_bridged_kiosk_rejected_before_start(self):
  config_module=types.ModuleType('vyos.config');config_module.Config=object
  vyos=types.ModuleType('vyos');vyos.ConfigError=ValueError
  with patch.dict(sys.modules,{'vyos':vyos,'vyos.config':config_module}):
   spec=importlib.util.spec_from_file_location('i_owner',Path(__file__).resolve().parents[1]/'cli/service.py')
   m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
   with self.assertRaisesRegex(ValueError,'allow-host-networks'):
    m.verify({'kiosk':'signage-i','_host_network':False})
   m.verify(None)
   m.verify({'disable':None})
