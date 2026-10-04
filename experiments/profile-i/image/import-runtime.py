#!/usr/bin/python3
import hashlib,json,os,subprocess
from pathlib import Path
BASE=Path('/usr/share/vyos-arm64-board-builder/signage-runtime')

def install(base=BASE):
    os.environ['CONTAINERS_STORAGE_CONF']=str(base/'storage.conf')
    meta=json.loads((base/'runtime.json').read_text())
    missing=False
    def identity(tag):
        p=subprocess.run(['podman','image','inspect','--format','{{.Id}}',tag],capture_output=True,text=True)
        return p.stdout.strip().removeprefix('sha256:') if p.returncode==0 else None
    for item in meta['images']:
        actual=identity(item['tag'])
        if actual is None:missing=True
        elif actual!=item['id'].removeprefix('sha256:'):raise ValueError('Versioned image tag has changed: '+item['tag'])
    if missing:
        archive=base/'runtime.tar'
        with archive.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=meta['archive_sha256']:raise ValueError('Archive checksum mismatch')
        subprocess.run(['podman','load','-i',str(archive)],check=True)
    for item in meta['images']:
        if identity(item['tag'])!=item['id'].removeprefix('sha256:'):raise ValueError('Imported image identity mismatch')

if __name__=='__main__':
    if not Path('/usr/lib/live/mount/persistence').is_mount():raise SystemExit('Persistent container storage is not mounted')
    install()
