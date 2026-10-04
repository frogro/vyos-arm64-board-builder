#!/usr/bin/python3
"""Explicit, checksum-pinned vendor installation; no proprietary binary in images."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import urllib.request

VERSION = '4.8.8'
URL = 'https://www.virtualhere.com/sites/default/files/usbserver/vhusbdarm64'
SHA256 = '09deced5586ed37b8b3db7a6187d84029f65d487c3c2b24a949b993b3d582077'
ROOT = Path('/config/profile-e/virtualhere-bin')
MAX_SIZE = 16 * 1024 * 1024


def validate(data):
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError('VirtualHere checksum mismatch; vendor file may have changed. Existing installation was not replaced.')
    # ELF64, little endian, AArch64. No execution before integrity validation.
    if data[:6] != b'\x7fELF\x02\x01' or int.from_bytes(data[18:20], 'little') != 183:
        raise ValueError('Expected an ELF64 AArch64 executable')


def install(data, root=ROOT):
    validate(data)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root.chmod(0o700)
    with tempfile.TemporaryDirectory(prefix='.install-', dir=root) as temporary:
        staged = Path(temporary)/'vhusbdarm64'
        staged.write_bytes(data)
        staged.chmod(0o700)
        destination = root/'vhusbdarm64'
        # Rename atomically; a running process retains the previous inode.
        # Preserve the former executable for an explicit rollback if upgraded.
        if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() != SHA256:
            shutil.copy2(destination, root/'vhusbdarm64.previous')
        staged.replace(destination)
        record = Path(temporary)/'installation.json'
        record.write_text(json.dumps(dict(version=VERSION, sha256=SHA256, source=URL), indent=2)+'\n')
        record.chmod(0o600)
        record.replace(root/'installation.json')
    return destination


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--from-file', type=Path, help='Verify and install an already downloaded vendor binary')
    args = p.parse_args()
    if os.geteuid() != 0:
        p.error('Run as root to install the shared server')
    if args.from_file:
        with args.from_file.open('rb') as stream:
            data = stream.read(MAX_SIZE+1)
    else:
        with urllib.request.urlopen(URL, timeout=60) as response:
            if not response.geturl().startswith('https://'):
                raise ValueError('Refusing a non-HTTPS vendor redirect')
            data = response.read(MAX_SIZE+1)
    if len(data) > MAX_SIZE:
        raise ValueError('Unexpected VirtualHere binary size')
    print('Installed verified VirtualHere', VERSION, 'at', install(data))
    print('Server remains disabled until explicitly configured. No license is included.')


if __name__ == '__main__':
    main()
