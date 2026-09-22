#!/usr/bin/env python3
"""Prepare native VyOS release feed only for an explicitly registered board/profile."""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def channel_for(board, profile):
    if not re.fullmatch(r'[a-z0-9-]+', board):
        raise ValueError('Invalid board identifier')
    path = ROOT / 'profiles/update-channels' / f'{board}.json'
    if profile != 'network' or not path.exists():
        return None
    channel = json.loads(path.read_text())
    assert channel['schema'] == 1 and channel['board'] == board and channel['profile'] == profile
    assert re.fullmatch(r'VyARM-Community/[a-z0-9-]+', channel['repository'])
    assert channel['url'] == f"https://github.com/{channel['repository']}/releases/latest/download/image-version.json"
    return channel

def prepare(board, profile, manifest, iso, tag, version, output):
    channel = channel_for(board, profile)
    if not channel:
        raise ValueError('No registered update channel for this board/profile')
    for field, expected in [('board',board),('profile',profile),('architecture','arm64')]:
        if manifest.get(field) != expected:
            raise ValueError(f'ISO manifest {field} mismatch')
    if not re.fullmatch(r'[A-Za-z0-9._-]+', tag) or not re.fullmatch(r'[A-Za-z0-9._-]+\.iso', iso.name):
        raise ValueError('Invalid release asset or tag')
    with iso.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    expected_sha = Path(str(iso)+'.sha256').read_text().split()[0]
    if sha != expected_sha:
        raise ValueError('ISO checksum mismatch')
    feed = [{'arch':'arm64', 'flavors':['generic'], 'image':iso.name, 'latest':True,
             'lts':False, 'release_date':datetime.now(timezone.utc).date().isoformat(),
             'release_train':'rolling', 'url':f"https://github.com/{channel['repository']}/releases/download/{tag}/{iso.name}",
             'version':version, 'sha256':sha, 'board':board, 'profile':profile}]
    output.write_text(json.dumps(feed, indent=2)+'\n')
    return channel

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('board'); p.add_argument('profile'); p.add_argument('--manifest',type=Path)
    p.add_argument('--iso',type=Path); p.add_argument('--tag'); p.add_argument('--version')
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.manifest:
        c=prepare(a.board,a.profile,json.loads(a.manifest.read_text()),a.iso,a.tag,a.version,a.output)
    else:
        c=channel_for(a.board,a.profile)
    print(c['repository'] if c else '')
