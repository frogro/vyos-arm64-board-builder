#!/usr/bin/env python3
"""Fail image assembly if the common modem contract is incomplete."""
import json
from pathlib import Path
import sys

MODULES = {'USB_NET_RNDIS_HOST': 'rndis_host', 'USB_NET_QMI_WWAN': 'qmi_wwan',
           'USB_NET_CDC_MBIM': 'cdc_mbim', 'USB_NET_CDC_NCM': 'cdc_ncm',
           'USB_NET_CDCETHER': 'cdc_ether', 'USB_SERIAL_OPTION': 'option',
           'USB_WDM': 'cdc_wdm'}
REQUIRED = tuple(MODULES)
COMMANDS = ('mmcli','mbimcli','qmicli','usb_modeswitch','pppd','dhclient')

def audit(root, config):
    values = dict(line.strip().split('=',1) for line in config.read_text().splitlines()
                  if line.startswith('CONFIG_') and '=' in line)
    missing = ['CONFIG_'+key for key in REQUIRED if values.get('CONFIG_'+key) not in ('y','m')]
    module_paths = [p.name.split('.ko')[0].replace('-', '_')
                    for p in (root/'usr/lib/modules').rglob('*.ko*') if p.is_file()]
    for key, name in MODULES.items():
        if values.get('CONFIG_'+key) == 'm' and name not in module_paths:
            missing.append(name+'.ko')
    # The image uses merged /usr. Reject links that resolve outside the image.
    def executable(path):
        return (path.resolve().is_relative_to(root.resolve()) and path.is_file()
                and bool(path.stat().st_mode & 0o111))
    for name in COMMANDS:
        if not any(executable(root/p/name)
                   for p in ('usr/bin','usr/sbin','bin','sbin') if not (root/p).is_symlink()):
            missing.append(name)
    return missing

if __name__ == '__main__':
    root, config = map(Path, sys.argv[1:3])
    missing = audit(root,config)
    dest=root/'usr/share/vyos-arm64-board-builder/modem-support.json'
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps({'required_symbols':list(REQUIRED),'required_commands':list(COMMANDS),'missing':missing},indent=2)+'\n')
    if missing: raise SystemExit('Incomplete modem support: '+', '.join(missing))
    print('PASS: common USB modem drivers and native modem tools present')
