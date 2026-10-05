import importlib.util,sys,types,unittest
from pathlib import Path
from unittest.mock import patch
class ServiceContract(unittest.TestCase):
 def owner(self):
  config_module=types.ModuleType('vyos.config');config_module.Config=object
  vyos=types.ModuleType('vyos');vyos.ConfigError=ValueError
  with patch.dict(sys.modules,{'vyos':vyos,'vyos.config':config_module}):
   spec=importlib.util.spec_from_file_location('i_owner',Path(__file__).resolve().parents[1]/'cli/service.py')
   m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
   return m

 def test_invalid_firewall_does_not_stop_existing_service(self):
  import subprocess
  m=self.owner()
  def run(*args,**kwargs):
   if args[:2]==('nft','--check'):raise subprocess.CalledProcessError(1,args)
  with patch.object(m,'run',side_effect=run) as calls,patch.object(m.subprocess,'run') as probe:
   probe.return_value.returncode=0
   with self.assertRaises(subprocess.CalledProcessError):m.apply({'allow_client':['192.168.178.0/24']})
   self.assertEqual(len(calls.call_args_list),1)

 def test_disabled_service_removes_only_its_own_firewall(self):
  m=self.owner()
  self.assertEqual(m.firewall_rules(None,True),'delete table inet vyarm_signage\n')
  self.assertEqual(m.firewall_rules({'disable':None},False),'')

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
