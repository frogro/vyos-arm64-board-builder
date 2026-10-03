#!/usr/bin/env python3
"""Firmware failure atomicity and compiled per-profile Pi DT selection."""
import hashlib,importlib.util,json,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('bt',ROOT/'tools/install-pi5-bluetooth.py');bt=importlib.util.module_from_spec(spec);spec.loader.exec_module(bt)
class Firmware(unittest.TestCase):
 def test_bad_checksum_leaves_root_unchanged(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);m={'files':{n:{'url':n,'sha256':hashlib.sha256(n.encode()).hexdigest()} for n in ['BCM4345C0.hcd','BCM4345C5.hcd']}}
   with self.assertRaises(ValueError):bt.install(root,m,lambda n:n.encode() if n.endswith('C0.hcd') else b'corrupt')
   self.assertEqual(list(root.iterdir()),[])
 def test_hcd_and_licence_installed_without_network_profile(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);names=['BCM4345C0.hcd','BCM4345C5.hcd','BCM-LEGAL.txt'];m={'files':{n:{'url':n,'sha256':hashlib.sha256(n.encode()).hexdigest()} for n in names}}
   bt.install(root,m,lambda n:n.encode())
   self.assertEqual((root/'usr/lib/firmware/brcm/BCM4345C5.hcd').read_bytes(),b'BCM4345C5.hcd')
   self.assertTrue((root/'usr/share/doc/vyarm-pi5-bluetooth/BCM-LEGAL.txt').is_file())
class DeviceTree(unittest.TestCase):
 @unittest.skipUnless(os.environ.get('PI5_TEST_DTB'),'Set PI5_TEST_DTB to a freshly compiled patched DTB')
 def test_a_is_host_safe_and_d_enables_only_usbc(self):
  source=os.environ['PI5_TEST_DTB'];node='/axi/usb@1000480000'
  def get(path,node,key):return subprocess.check_output(['fdtget',path,node,key],text=True).strip()
  self.assertEqual(get(source,node,'status'),'disabled')
  with tempfile.TemporaryDirectory() as d:
   overlay=d+'/gadget.dtbo';target=d+'/kvm.dtb'
   subprocess.run(['dtc','-@','-I','dts','-O','dtb','-o',overlay,str(ROOT/'profiles/kvm-hardware/dt-overlays/pi5-usbc-peripheral.dts')],check=True)
   subprocess.run(['fdtoverlay','-i',source,'-o',target,overlay],check=True)
   self.assertEqual(get(target,node,'status'),'okay')
   self.assertEqual(get(target,node,'dr_mode'),'peripheral')
   self.assertEqual(get(source,node,'status'),'disabled')
   # RP1 host controllers must remain host when USB-C is switched to gadget.
   text=subprocess.check_output(['dtc','-I','dtb','-O','dts',target],stderr=subprocess.DEVNULL,text=True)
   self.assertEqual(text.count('dr_mode = "host"'),2)
if __name__=='__main__':unittest.main()
