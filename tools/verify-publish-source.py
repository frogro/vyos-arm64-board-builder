#!/usr/bin/env python3
"""Accept completed builds, including failures confined to release publication."""
import json,subprocess,sys

def validate(source, jobs):
    if source.get('status') != 'completed':
        raise ValueError('Source build is not completed')
    if source.get('conclusion') == 'success':
        return source['head_sha']
    if source.get('conclusion') != 'failure':
        raise ValueError('Source build was cancelled or incomplete')
    failures=[j for j in jobs if j.get('conclusion')=='failure']
    if len(failures)!=1 or failures[0]['name']!='board-image':
        raise ValueError('Failure outside board publication')
    steps=failures[0]['steps']
    failed={s['name'] for s in steps if s.get('conclusion')=='failure'}
    if not failed or not failed <= {'Publish GitHub release','Publish registered board update channel'}:
        raise ValueError('Build or validation failed')
    required={'Assemble VyOS board image','Verify complete board SD/eMMC rootfs before ISO packaging','Create VyOS system-image update ISO','Compress board image','Upload board candidate'}
    passed={s['name'] for s in steps if s.get('conclusion')=='success'}
    if not required<=passed:
        raise ValueError('Missing successful build, validation or artifact upload')
    return source['head_sha']

if __name__=='__main__':
    repo,run=sys.argv[1:]
    if not run.isdigit():raise SystemExit('Invalid source run')
    source=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{run}'],text=True))
    jobs=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{run}/jobs?per_page=100'],text=True))['jobs']
    print(validate(source,jobs))
