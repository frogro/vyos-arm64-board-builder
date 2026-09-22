#!/usr/bin/env python3
"""Bundle verified official ARM64 binaries into an offline image, without state."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import urllib.request

BASE = 'https://pkgs.tailscale.com/stable/'
LIMIT = 128 * 1024 * 1024


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'vyos-arm64-board-builder'})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ValueError('Tailscale download exceeds size limit')
    return data


def unpack(archive, version, digest):
    if not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise ValueError('Invalid official SHA256')
    if hashlib.sha256(archive).hexdigest() != digest:
        raise ValueError('Tailscale archive checksum mismatch')
    binaries = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
        for name in ('tailscale', 'tailscaled'):
            expected = f'tailscale_{version}_arm64/{name}'
            matches = [member for member in tar.getmembers() if member.name == expected]
            if len(matches) != 1 or not matches[0].isfile() or not 64 <= matches[0].size <= LIMIT:
                raise ValueError('Missing, duplicate or unsafe binary: ' + name)
            data = tar.extractfile(matches[0]).read()
            # ELF64 little-endian, EM_AARCH64=183. Never run downloaded code on
            # the development host and never extract arbitrary archive paths.
            if data[:6] != b'\x7fELF\x02\x01' or data[18:20] != b'\xb7\x00':
                raise ValueError('Not a Linux ARM64 ELF binary: ' + name)
            binaries[name] = data
    return binaries


def install(root, version=None, download=fetch):
    root = root.resolve()
    if root == Path('/') or not (root / 'etc').is_dir():
        raise ValueError('Expected an offline image rootfs')
    release = json.loads(download(BASE + '?mode=json'))
    latest = release['TarballsVersion']
    selected = version or latest
    for value in (latest, selected):
        if not re.fullmatch(r'\d+\.\d+\.\d+', value):
            raise ValueError('Invalid stable release version')
    filename = f'tailscale_{selected}_arm64.tgz'
    if version is None and release['Tarballs']['arm64'] != filename:
        raise ValueError('Official ARM64 release metadata mismatch')
    url = BASE + filename
    digest = download(url + '.sha256').decode().strip().split()[0]
    binaries = unpack(download(url), selected, digest)
    destination = root / 'usr/libexec/tailscale'
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in binaries.items():
        target = destination / name
        if target.is_symlink():
            raise ValueError('Refusing binary symlink: ' + str(target))
        target.write_bytes(data)
        target.chmod(0o755)
    metadata = {'version': selected, 'latest_stable_at_build': latest,
                'version_pinned': version is not None, 'architecture': 'arm64',
                'url': url, 'sha256': digest,
                'checked_at': datetime.now(timezone.utc).isoformat(),
                'binaries': {name: hashlib.sha256(data).hexdigest() for name, data in binaries.items()}}
    provenance = root / 'usr/share/vyos-arm64-board-builder/tailscale'
    provenance.mkdir(parents=True, exist_ok=True)
    (provenance / 'build.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(f'Bundled official Tailscale {selected} ARM64; latest stable {latest}; SHA256 {digest}')
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rootfs', type=Path)
    parser.add_argument('--version', help='Explicit version for a reproducible rebuild; still checks latest stable')
    args = parser.parse_args()
    install(args.rootfs, args.version)
