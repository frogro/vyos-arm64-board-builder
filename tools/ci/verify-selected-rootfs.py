#!/usr/bin/env python3
"""Check selected and unselected payloads, identity, and board USB routing."""
import json,os,subprocess,sys

def validate(read, present, env):
    enabled=lambda name:env.get(name,'no') in ('yes','true')
    features={'extended_network':enabled('EXTENDED_NETWORK'),
              'tailscale_subnet_router':enabled('TAILSCALE_SUBNET_ROUTER'),
              'kvm_over_ip':enabled('KVM_OVER_IP'),
              'kiosk_f':enabled('KIOSK_F'),'receiver_g':enabled('RECEIVER_G'),'print_server_e':enabled('PRINT_SERVER_E'),'signage_i':enabled('SIGNAGE_I')}
    metadata=json.loads(read('usr/share/vyos-arm64-board-builder/profile.json'))
    assert metadata['board']==env['BOARD']
    for name,value in features.items():assert bool(metadata['features'].get(name,False))==value,(name,value)
    for feature,path in [
        ('tailscale_subnet_router','usr/libexec/vyos/conf_mode/service_tailscale.py'),
        ('kvm_over_ip','usr/libexec/vyos/conf_mode/service_kvm_over_ip.py'),
        ('kiosk_f','usr/share/vyos-arm64-board-builder/kiosk-runtime/runtime.json'),
        ('receiver_g','usr/share/vyos-arm64-board-builder/receiver-runtime/runtime.json'),
        ('print_server_e','usr/share/vyos-arm64-board-builder/print-runtime/runtime.json'),
        ('signage_i','usr/share/vyos-arm64-board-builder/signage-runtime/runtime.json'),
        ('signage_i','usr/libexec/vyos/conf_mode/service_signage.py'),
        ('print_server_e','usr/libexec/vyos/conf_mode/service_print_server.py')]:
        assert present(path)==features[feature],(feature,path)
    assert present('usr/libexec/vyos/conf_mode/service_usb_server.py') == (features['receiver_g'] or features['print_server_e'])
    for feature,folder,key in [('kiosk_f','kiosk-runtime','builder_commit'),('receiver_g','receiver-runtime','source_commit'),('print_server_e','print-runtime','source_commit'),('signage_i','signage-runtime','source_commit')]:
        if features[feature]:
            data=json.loads(read('usr/share/vyos-arm64-board-builder/'+folder+'/runtime.json'))
            assert data[key]==env['GITHUB_SHA'],folder
    if features['kvm_over_ip']:
        if env['BOARD']=='radxa-e52c':
            raise AssertionError('E52C supports A-C only; unexpected D payload')
        routing=read('usr/share/vyos-arm64-board-builder/kvm-gadget-provider.env')
        if env['BOARD']=='orangepi5-plus':assert 'fc000000.usb' in routing and 'fc400000' not in routing
        elif env['BOARD']=='raspberry-pi-5':assert '1000480000.usb' in routing and 'fc400000' not in routing
        elif env['BOARD']=='rock-5b':assert 'fc000000.usb' in routing and 'fc400000' not in routing
    print('PASS: selected payloads, excluded payloads, provenance and gadget routing')

if __name__=='__main__':
    squash=sys.argv[1]
    listing=subprocess.check_output(['unsquashfs','-ll',squash],text=True)
    paths={line.split('squashfs-root/',1)[1].split(' -> ',1)[0] for line in listing.splitlines() if 'squashfs-root/' in line}
    def read(path):return subprocess.check_output(['unsquashfs','-cat',squash,path],text=True)
    validate(read,lambda p:p in paths,os.environ)
