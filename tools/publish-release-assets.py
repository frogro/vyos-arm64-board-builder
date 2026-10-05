#!/usr/bin/env python3
"""Publish only complete, checksum-verified releases; split large install images."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

LIMIT = 2147483648
CHUNK = 1500 * 1024 * 1024


def split_image(path, directory, limit=LIMIT, chunk=CHUNK):
    if path.stat().st_size < limit:
        return [path]
    if not path.name.endswith('.img.xz'):
        raise ValueError(f'{path.name} exceeds the download limit; only IMG files can be split')
    parts = []
    with path.open('rb') as source:
        while True:
            block = source.read(min(chunk, 8*1024*1024))
            if not block:
                break
            part = directory / f'{path.name}.part{len(parts)+1:02d}'
            with part.open('wb') as dest:
                dest.write(block)
                remaining = chunk-len(block)
                while remaining:
                    block = source.read(min(remaining, 8*1024*1024))
                    if not block:
                        break
                    dest.write(block)
                    remaining -= len(block)
            parts.append(part)
    return parts


def publish(repo, tag, sha, title, notes, assets):
    def gh(*args):
        return subprocess.check_output(['gh', *args], text=True)
    with tempfile.TemporaryDirectory(prefix='release-assets-') as tmp:
        directory = Path(tmp)
        upload = []
        text = notes.read_text()
        for path in assets:
            parts = split_image(path, directory)
            upload.extend(parts)
            if parts != [path]:
                text += ('\nInstallation image is split. Download every part and the original checksum, then join:\n```sh\ncat '
                         + ' '.join(p.name for p in parts) + ' > ' + path.name
                         + '\nsha256sum -c ' + path.name + '.sha256\n```\nDo not flash individual parts.\n')
        # Reject colliding names before creating or altering any release.
        if len({p.name for p in upload}) != len(upload):
            raise ValueError('Duplicate release asset names')
        expected = {}
        for path in upload:
            with path.open('rb') as stream:
                expected[path.name] = hashlib.file_digest(stream, 'sha256').hexdigest()
        note_file = directory/'notes.md'; note_file.write_text(text)
        result = subprocess.run(['gh','release','view',tag,'-R',repo,'--json','isDraft'], capture_output=True,text=True)
        if result.returncode == 0:
            if not json.loads(result.stdout)['isDraft']:
                raise ValueError('Release is already published; refusing replacement')
            gh('release','edit',tag,'-R',repo,'--notes-file',str(note_file))
        else:
            gh('release','create',tag,'-R',repo,'--target',sha,'--draft','--title',title,'--notes-file',str(note_file))
        for path in upload:
            for attempt in range(4):
                result = subprocess.run(['gh','release','upload',tag,'-R',repo,str(path),'--clobber'])
                if result.returncode == 0:
                    break
                if attempt == 3:
                    raise RuntimeError(f'Upload failed: {path.name}')
                time.sleep(5*(attempt+1))
        # Draft releases without a Git tag are absent from the tag endpoint.
        pages = json.loads(gh('api', '--paginate', '--slurp', f'repos/{repo}/releases?per_page=100'))
        remote = next(r for page in pages for r in page if r['tag_name'] == tag)
        actual = {a['name']:a.get('digest') for a in remote['assets'] if a['state']=='uploaded'}
        if any(actual.get(name) != 'sha256:'+digest for name,digest in expected.items()):
            raise ValueError('Remote asset checksums do not match')
        gh('release','edit',tag,'-R',repo,'--draft=false','--latest')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for key in ('repo','tag','sha','title','notes'): parser.add_argument('--'+key, required=True)
    parser.add_argument('assets',nargs='+',type=Path)
    args = parser.parse_args()
    publish(args.repo,args.tag,args.sha,args.title,Path(args.notes),args.assets)
