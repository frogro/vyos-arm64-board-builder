#!/usr/bin/env python3
"""Install pinned onboard Pi Bluetooth firmware, independent of profile B."""
import hashlib,json,sys,urllib.request
from pathlib import Path

def install(root, manifest, fetch):
    # Verify every input before changing the rootfs.
    data={}
    for name, item in manifest['files'].items():
        if name not in ('BCM4345C0.hcd','BCM4345C5.hcd','BCM-LEGAL.txt'):
            raise ValueError('Unexpected firmware filename')
        blob=fetch(item['url'])
        if hashlib.sha256(blob).hexdigest()!=item['sha256']:
            raise ValueError('Pi Bluetooth firmware checksum mismatch: '+name)
        data[name]=blob
    for name,blob in data.items():
        relative=('usr/share/doc/vyarm-pi5-bluetooth/' if name.endswith('.txt') else 'usr/lib/firmware/brcm/')+name
        target=root/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(blob)
    target=root/'usr/share/vyos-arm64-board-builder/pi5-bluetooth.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(manifest,indent=2)+'\n')

if __name__=='__main__':
    manifest=Path(__file__).resolve().parents[1]/'profiles/base-hardware/raspberry-pi-5-bluetooth.json'
    install(Path(sys.argv[1]),json.loads(manifest.read_text()),lambda url:urllib.request.urlopen(url,timeout=60).read())
