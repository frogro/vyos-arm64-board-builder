#!/usr/bin/env python3
"""Import a versioned offline print image without changing saved configuration."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/usr/share/vyos-arm64-board-builder/print-runtime')


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def install(root=ROOT, run=subprocess.run):
    meta = json.loads((root / 'runtime.json').read_text())
    archive = root / 'runtime.tar'
    tag = meta['tag']
    expected = meta['image_id'].removeprefix('sha256:')
    if not tag.startswith('localhost/vyarm-print:') or len(expected) != 64:
        raise ValueError('Invalid runtime identity')
    if run(['podman', 'image', 'exists', tag], check=False).returncode == 0:
        actual = run(['podman', 'image', 'inspect', '--format', '{{.Id}}', tag],
                     check=True, capture_output=True, text=True).stdout.strip().removeprefix('sha256:')
        if actual != expected:
            raise ValueError('Versioned print tag already points to another image; refusing replacement')
        print('Offline print runtime already present:', tag)
        return
    if digest(archive) != meta['archive_sha256']:
        raise ValueError('Offline print archive checksum mismatch')
    run(['podman', 'load', '--input', str(archive)], check=True)
    actual = run(['podman', 'image', 'inspect', '--format', '{{.Id}}', tag],
                 check=True, capture_output=True, text=True).stdout.strip().removeprefix('sha256:')
    if actual != expected:
        raise ValueError('Imported print image identity mismatch')
    print('Imported offline print runtime:', tag)


if __name__ == '__main__':
    if not Path('/usr/lib/live/mount/persistence').is_mount():
        raise SystemExit('Persistent container storage is not mounted')
    # E can run without any native container configuration; use the same
    # persistent store for import, owner validation and the CUPS supervisor.
    os.environ['CONTAINERS_STORAGE_CONF'] = str(ROOT / 'storage.conf')
    install()
