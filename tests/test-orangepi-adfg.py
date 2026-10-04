#!/usr/bin/env python3
"""Orange Pi integration checks; explicitly not a live hardware test."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]

class Integration(unittest.TestCase):
    def test_all_profiles_selected(self):
        with tempfile.TemporaryDirectory() as temp:
            env=Path(temp)/'profile.env'; meta=Path(temp)/'profile.json'
            subprocess.run(['python3',str(ROOT/'tools/feature-profile.py'),
                '--extended-network','yes','--tailscale-subnet-router','yes',
                '--kvm-over-ip','yes','--kiosk-f','yes','--receiver-g','yes',
                '--output-env',str(env),'--output-json',str(meta)],check=True)
            self.assertEqual(json.loads(meta.read_text())['profile'], 'network-tailscale-kvm-kiosk-receiver')
            self.assertIn('RECEIVER_G=yes',env.read_text())
        self.assertIn('--receiver-g "${RECEIVER_G:-no}"', (ROOT/'build.sh').read_text())

    def test_board_routing_is_not_copied_from_rock(self):
        rows=(ROOT/'profiles/kvm-hardware-providers.conf').read_text().splitlines()
        row=next(line.split('|') for line in rows if line.startswith('orangepi5-plus|'))
        self.assertEqual(row[1],'rk3588-synopsys-hdmirx')
        self.assertEqual(row[5],'runtime')
        text=(ROOT/row[6]).read_text()
        self.assertNotIn('dr_mode',text)
        self.assertNotIn('fc400000',text)
        for path in ['/mpp-srv','/rkvenc-ccu','/rkvenc-core@fdbd0000','/rkvenc-core@fdbe0000']:
            self.assertIn('target-path = "'+path+'"',text)
        self.assertIn('orangepi5-plus|edk2-rk3588', (ROOT/'profiles/firmware-providers.conf').read_text())

    def test_actual_runtime_routing_selection(self):
        text=(ROOT/'tools/finalize-vyos-rootfs.sh').read_text()
        block=text.split('    KVM_GADGET_PROVIDER_SOURCE=',1)[1].split('    if [[ -f "$KVM_GADGET_PROVIDER_SOURCE" ]]; then',1)[0]
        block='KVM_GADGET_PROVIDER_SOURCE='+block
        for board,port,udc in [('orangepi5-plus','usbc','fc000000.usb'),('rock-5b','usbc','fc000000.usb')]:
            code='ROOT="$1"; BOARD="$2"; KVM_HARDWARE_PROVIDER=rk3588-synopsys-hdmirx;\n'+block+'\nsource "$KVM_GADGET_PROVIDER_SOURCE"; key="KVM_GADGET_UDC_${KVM_GADGET_DEFAULT_PORT^^}"; printf "%s %s" "$KVM_GADGET_DEFAULT_PORT" "${!key}"'
            result=subprocess.check_output(['bash','-ec',code,'test',str(ROOT),board],text=True)
            self.assertEqual(result,port+' '+udc)

    def test_old_ab_selection_preserved(self):
        spec=importlib.util.spec_from_file_location('features',ROOT/'tools/feature-profile.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual(module.derive(True,False,False)['features'],
            {'extended_network':True,'tailscale_subnet_router':False,'kvm_over_ip':False})

if __name__=='__main__': unittest.main()
