#!/usr/bin/env python3
"""Stage F host fixes into a live or image root; never starts services."""
import argparse
import hashlib
from pathlib import Path
import urllib.request

REV = '2b8daaf611fbade74f26a5b58ec1defe6a02f5e0'
BASE = f'https://gitlab.com/kernel-firmware/linux-firmware/-/raw/{REV}/'
ASSETS = {
    'arm/mali/arch10.8/mali_csffw.bin': 'a27847ea11f8efb3136340c3ba8aab413ae25145eeb4a7f64ff5edd829a2405b',
    'LICENSES/LICENCE.mali_csffw': 'ebedc86d1767186a66dcb59ce8dcb97c5fd9ac10de2adaacad226714e4712f6d',
}
DROPIN = '''# VyARM F: timezone is applied before syslog generates its runtime config.
[Unit]
ConditionPathExists=/run/rsyslog/rsyslog.conf
'''
HOOK = '''#!/bin/sh
set -eu
case "${1:-}" in prereqs) exit 0;; esac
for rel in arm/mali/arch10.8/mali_csffw.bin LICENSES/LICENCE.mali_csffw; do
    test -s "/usr/lib/firmware/$rel"
    mkdir -p "$DESTDIR/usr/lib/firmware/$(dirname "$rel")"
    cp -p "/usr/lib/firmware/$rel" "$DESTDIR/usr/lib/firmware/$rel"
done
'''

def install(root, cache, panthor=False):
    root = Path(root).resolve(strict=True)
    files = {'etc/systemd/system/rsyslog.service.d/50-vyarm-config-ready.conf': (DROPIN.encode(), 0o644)}
    if panthor:
        cache = Path(cache)
        cache.mkdir(parents=True, exist_ok=True)
        for rel, digest in ASSETS.items():
            local = cache / Path(rel).name
            data = local.read_bytes() if local.exists() else urllib.request.urlopen(BASE + rel, timeout=60).read()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError(f'Firmware checksum mismatch: {rel}')
            if not local.exists():
                local.write_bytes(data)
            files['usr/lib/firmware/' + rel] = (data, 0o644)
        files['etc/initramfs-tools/hooks/vyarm-panthor-firmware'] = (HOOK.encode(), 0o755)
    for rel, (data, mode) in files.items():
        path = root / rel
        resolved = path.resolve()
        if root != Path('/') and root not in resolved.parents:
            raise ValueError(f'Destination escapes root: {path}')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(mode)
        print(path)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rootfs', required=True)
    parser.add_argument('--cache', default='/tmp/vyarm-gpu-firmware')
    parser.add_argument('--panthor-arch10-8', action='store_true', help='Include Mali arch10.8 firmware for a matching GPU; do not enable for every SBC')
    args = parser.parse_args()
    install(args.rootfs, args.cache, args.panthor_arch10_8)
