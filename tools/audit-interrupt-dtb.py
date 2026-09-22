#!/usr/bin/env python3
"""Record the final DTB's GIC coherency contract; reject broken RK358x trees."""
import argparse
import json
from pathlib import Path
import subprocess


def fdt(dtb, *args):
    return subprocess.run(['fdtget', *args[:1], str(dtb), *args[1:]], capture_output=True, text=True)


def audit(dtb):
    compatibles = fdt(dtb, '-ts', '/', 'compatible').stdout.split()
    rk358x = any(x in compatibles for x in ('rockchip,rk3588','rockchip,rk3588s','rockchip,rk3582'))
    pending, nodes = ['/'], []
    while pending:
        path = pending.pop()
        compatible = fdt(dtb, '-ts', path, 'compatible').stdout.split()
        if any(c in compatible for c in ('arm,gic-v3', 'arm,gic-v3-its')):
            properties = fdt(dtb, '-p', path).stdout.split()
            nodes.append(dict(path=path, compatible=compatible,
                dma_noncoherent='dma-noncoherent' in properties,
                dma_coherent='dma-coherent' in properties))
        pending.extend(path.rstrip('/') + '/' + child for child in fdt(dtb, '-l', path).stdout.split())
    errors = []
    if rk358x:
        if not nodes: errors.append('RK358x DTB has no GIC nodes')
        for node in nodes:
            if not node['dma_noncoherent'] or node['dma_coherent']:
                errors.append('Missing/contradictory RK358x coherency: ' + node['path'])
    return dict(compatible=compatibles, rk358x=rk358x, interrupt_controllers=nodes, errors=errors)


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('dtb',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    if not args.dtb.is_file():raise SystemExit('DTB missing')
    report=audit(args.dtb);args.output.write_text(json.dumps(report,indent=2)+'\n')
    if report['errors']:raise SystemExit('; '.join(report['errors']))
