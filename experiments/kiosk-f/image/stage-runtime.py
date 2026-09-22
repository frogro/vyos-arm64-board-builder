#!/usr/bin/env python3
"""Stage an offline runtime into a new image root, never into persistent /config."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent


def stage(root, artifacts):
    root = root.resolve(strict=True)
    if root == Path('/'):
        raise ValueError('Offline root required')
    meta = json.loads((artifacts / 'runtime.json').read_text())
    archive = artifacts / 'runtime.tar'
    with archive.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != meta['archive_sha256']:
        raise ValueError('Runtime archive checksum mismatch')
    for source, target, mode in [
        (HERE / 'kiosk-generator.py', 'usr/lib/systemd/system-generators/vyarm-kiosk-generator', 0o755),
        (HERE.parent / 'systemd/reconcile-inputs.py', 'usr/local/libexec/vyos-kiosk-reconcile-inputs', 0o755),
        (HERE.parent / 'systemd/wait-container-addresses.py', 'usr/local/libexec/vyos-kiosk-wait-addresses', 0o755),
        (HERE / 'storage.conf', 'usr/share/vyos-arm64-board-builder/kiosk-runtime/storage.conf', 0o644),
        (archive, 'usr/share/vyos-arm64-board-builder/kiosk-runtime/runtime.tar', 0o644),
        (artifacts / 'runtime.json', 'usr/share/vyos-arm64-board-builder/kiosk-runtime/runtime.json', 0o644),
        (HERE / 'import-runtime.py', 'usr/libexec/vyos/vyarm-kiosk-runtime-import', 0o755),
        (HERE / 'vyarm-kiosk-runtime.service', 'etc/systemd/system/vyarm-kiosk-runtime.service', 0o644),
    ]:
        dest = root / target
        if root not in dest.resolve().parents:
            raise ValueError('Destination escapes offline root')
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        dest.chmod(mode)
    link = root / 'etc/systemd/system/vyos.target.wants/vyarm-kiosk-runtime.service'
    link.parent.mkdir(parents=True, exist_ok=True)
    if not link.is_symlink():
        link.symlink_to('../vyarm-kiosk-runtime.service')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('artifacts', type=Path)
    args = parser.parse_args()
    stage(args.root, args.artifacts)
