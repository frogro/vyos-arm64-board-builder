#!/usr/bin/env python3
import importlib.util,itertools,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
plan=load('plan','tools/ci/multimedia-plan.py').plan
validate=load('verify','tools/ci/verify-selected-rootfs.py').validate
class Selection(unittest.TestCase):
 def test_all_32_combinations_preserve_selection(self):
  for values in itertools.product((False,True),repeat=5):
   for board in ['rock-5b','orangepi5-plus']:
    p=plan(board,*values)
    self.assertEqual(tuple(p[k] for k in ['network','tailscale','kvm','kiosk','receiver']),values)
    self.assertEqual(p['graphics'],values[3] or values[4])
    self.assertEqual(p['cached_copy'],values[2] and (values[3] or values[4]))
 def test_no_implicit_support_for_other_boards(self):
  for board in ['raspberry-pi-5','radxa-e52c']:
   plan(board,True,True,True)
   with self.assertRaises(ValueError):plan(board,kiosk=True)
   with self.assertRaises(ValueError):plan(board,receiver=True)
 def test_rootfs_selection_and_unselected_payloads(self):
  keys=['extended_network','tailscale_subnet_router','kvm_over_ip','kiosk_f','receiver_g']
  vars=['EXTENDED_NETWORK','TAILSCALE_SUBNET_ROUTER','KVM_OVER_IP','KIOSK_F','RECEIVER_G']
  for values in itertools.product((False,True),repeat=5):
   env=dict(zip(vars,['yes' if v else 'no' for v in values]),BOARD='orangepi5-plus',GITHUB_SHA='abc')
   data={'usr/share/vyos-arm64-board-builder/profile.json':json.dumps(dict(board='orangepi5-plus',features=dict(zip(keys,values))))}
   if values[1]:data['usr/libexec/vyos/conf_mode/service_tailscale.py']=''
   if values[2]:
    data['usr/libexec/vyos/conf_mode/service_kvm_over_ip.py']=''
    data['usr/share/vyos-arm64-board-builder/kvm-gadget-provider.env']='KVM_GADGET_UDC_USBC=fc000000.usb'
   for selected,folder,key in [(values[3],'kiosk-runtime','builder_commit'),(values[4],'receiver-runtime','source_commit')]:
    if selected:data['usr/share/vyos-arm64-board-builder/'+folder+'/runtime.json']=json.dumps({key:'abc'})
   validate(data.__getitem__,data.__contains__,env)
   if not values[4]:
    data['usr/share/vyos-arm64-board-builder/receiver-runtime/runtime.json']='{}'
    with self.assertRaises(AssertionError):validate(data.__getitem__,data.__contains__,env)
if __name__=='__main__':unittest.main()
