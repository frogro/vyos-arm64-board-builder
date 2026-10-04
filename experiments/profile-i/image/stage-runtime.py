#!/usr/bin/python3
import hashlib,json,re,shutil,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent

def stage(root,artifacts):
    root=Path(root).resolve(strict=True);artifacts=Path(artifacts)
    if root==Path('/'):raise ValueError('Offline root required')
    meta=json.loads((artifacts/'runtime.json').read_text());info=json.loads((artifacts/'image.json').read_text())
    if meta.get('profile')!='signage-i' or not re.fullmatch(r'localhost/vyarm-signage:i-[a-f0-9]+',meta['tag']):raise ValueError('Wrong runtime')
    if meta['redis_tag']!='localhost/vyarm-signage-redis:22448b474134':raise ValueError('Wrong Redis runtime')
    if len(info)!=2 or any(i['Architecture']!='arm64' for i in info):raise ValueError('Wrong runtime architecture')
    for item,tag in zip(info,(meta['tag'],meta['redis_tag'])):
        if tag not in item['RepoTags']:raise ValueError('Missing image tag')
    if info[0]['Config']['Labels'].get('io.vyarm.signage.version')!='1':raise ValueError('Wrong image capability')
    if meta['images']!=[{'tag':tag,'id':i['Id']} for i,tag in zip(info,(meta['tag'],meta['redis_tag']))]:raise ValueError('Image identity mismatch')
    with (artifacts/'runtime.tar').open('rb') as f:
        if hashlib.file_digest(f,'sha256').hexdigest()!=meta['archive_sha256']:raise ValueError('Archive checksum mismatch')
    base=root/'usr/share/vyos-arm64-board-builder/signage-runtime'
    if root not in base.resolve().parents:raise ValueError('Destination escapes root')
    base.mkdir(parents=True,exist_ok=True)
    for name in ('runtime.json','runtime.tar','image.json'):shutil.copyfile(artifacts/name,base/name)
    shutil.copyfile(HERE.parents[1]/'kiosk-f/image/storage.conf',base/'storage.conf')
    shutil.copytree(HERE.parent/'adapter',base/'adapter',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for src,dst,mode in [('import-runtime.py','usr/libexec/vyos/vyarm-signage-runtime-import',0o755),('vyarm-signage-runtime.service','etc/systemd/system/vyarm-signage-runtime.service',0o644)]:
        p=root/dst
        if root not in p.resolve().parents:raise ValueError('Destination escapes root')
        p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(HERE/src,p);p.chmod(mode)
    p=root/'etc/systemd/system/vyos.target.wants/vyarm-signage-runtime.service'
    p.parent.mkdir(parents=True,exist_ok=True)
    if not p.is_symlink():p.symlink_to('../vyarm-signage-runtime.service')

if __name__=='__main__':stage(*sys.argv[1:])
