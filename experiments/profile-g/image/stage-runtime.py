#!/usr/bin/env python3
"""Stage G beside F; import the image at boot without enabling a receiver."""
import hashlib,json,re,shutil,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent

def stage(root, artifacts):
    root=Path(root).resolve(strict=True);artifacts=Path(artifacts)
    if root==Path('/'):
        raise ValueError('Offline image root required')
    meta=json.loads((artifacts/'runtime.json').read_text())
    inspect=json.loads((artifacts/'image.json').read_text())[0]
    if meta.get('profile')!='receiver-g' or not re.fullmatch(r'localhost/vyarm-receiver:g-[a-f0-9]+',meta['tag']):
        raise ValueError('Wrong receiver runtime')
    if inspect['Architecture']!='arm64' or inspect['Config']['Labels'].get('io.vyarm.receiver.version')!='1':
        raise ValueError('Incompatible receiver image')
    if meta['tag'] not in inspect['RepoTags']:
        raise ValueError('Receiver tag missing from image metadata')
    with (artifacts/'runtime.tar').open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=meta['archive_sha256']:
            raise ValueError('Receiver archive checksum mismatch')
    meta['image_id']=inspect['Id']
    base='usr/share/vyos-arm64-board-builder/receiver-runtime/'
    for source,target,mode in [
        (artifacts/'runtime.tar',base+'runtime.tar',0o644),
        (artifacts/'image.json',base+'image.json',0o644),
        (HERE.parents[1]/'kiosk-f/image/storage.conf',base+'storage.conf',0o644),
        (HERE/'import-runtime.py','usr/libexec/vyos/vyarm-receiver-runtime-import',0o755),
        (HERE/'vyarm-receiver-runtime.service','etc/systemd/system/vyarm-receiver-runtime.service',0o644)]:
        dest=root/target
        if root not in dest.resolve().parents:raise ValueError('Destination escapes root')
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest);dest.chmod(mode)
    dest=root/base/'runtime.json'
    if root not in dest.resolve().parents:raise ValueError('Destination escapes root')
    dest.write_text(json.dumps(meta,indent=2)+'\n');dest.chmod(0o644)
    link=root/'etc/systemd/system/vyos.target.wants/vyarm-receiver-runtime.service'
    if root not in link.parent.resolve().parents:raise ValueError('Destination escapes root')
    link.parent.mkdir(parents=True,exist_ok=True)
    if not link.is_symlink():link.symlink_to('../vyarm-receiver-runtime.service')

if __name__=='__main__':stage(*sys.argv[1:])
