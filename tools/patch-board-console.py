#!/usr/bin/env python3
"""Extend only the serial-speed node of the installed VyOS reference/CLI."""
import argparse
import json
from pathlib import Path

OLD = '(1200|2400|4800|9600|19200|38400|57600|115200)'
NEW = '(1200|2400|4800|9600|19200|38400|57600|115200|1500000)'


def patch(root):
    path = root / 'usr/share/vyos/reftree.cache'
    reference = json.loads(path.read_text())
    node = reference
    for name in ('system', 'console', 'device', 'speed'):
        matches = [child for child in node['children'] if child['name'] == name]
        if len(matches) != 1: raise RuntimeError('Unsupported serial reference tree')
        node = matches[0]
    data = node['data']
    if data['constraints'] not in ([['regex', OLD]], [['regex', NEW]]):
        raise RuntimeError('Serial speed constraint changed upstream')
    data['constraints'] = [['regex', NEW]]
    for item in data['completion_help']:
        if item[0] == 'list' and '1500000' not in item[1].split():
            item[1] += ' 1500000'
    if not any(item[0] == '1500000' for item in data['value_help']):
        data['value_help'].append(['1500000', '1500000 bps'])
    template = root / 'opt/vyatta/share/vyatta-cfg/templates/system/console/device/node.tag/speed/node.def'
    text = template.read_text()
    if NEW not in text:
        if text.count(OLD) != 1: raise RuntimeError('Unsupported serial CLI template')
        text = text.replace(OLD, NEW)
        text = text.replace('57600 115200"', '57600 115200 1500000"')
        text += 'val_help: 1500000; 1500000 bps\n'
    # Python xml_ref keeps node type/default/owner only; they are unchanged.
    path.write_text(json.dumps(reference, separators=(',', ':')))
    template.write_text(text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('rootfs', type=Path)
    patch(parser.parse_args().rootfs)
