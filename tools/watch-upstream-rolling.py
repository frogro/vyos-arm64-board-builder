#!/usr/bin/env python3
"""Poll official releases and persist successful dispatches on the default branch."""
import base64
import json
import os
import re
import subprocess
from datetime import datetime

REPO = 'frogro/vyos-arm64-board-builder'
STATE = '.github/rolling-build-state.json'
BOARDS = {'radxa-e52c':'uboot-extlinux', 'rock-5b':'efi-firmware-dtb', 'raspberry-pi-5':'firmware-files'}
ARMBIAN = '9de7be05323564424cf64171cb483712ec356bc1'

def gh(*args):
    return subprocess.check_output(['gh',*args],text=True).strip()

def api(path):
    return json.loads(gh('api',path))

def pending(releases, state):
    # Tags sort chronologically in the official YYYY.MM.DD-HHMM format.
    return sorted((r for r in releases if not r.get('draft') and not r.get('prerelease')
        and re.fullmatch(r'\d{4}\.\d{2}\.\d{2}-\d{4}-rolling',r['tag_name'])
        and r['tag_name'] > state['baseline']),key=lambda r:r['tag_name'])

def title(board, tag):
    return f'{board} / {tag} / network=true tailscale=false kvm=false'

def main():
    item=api(f'repos/{REPO}/contents/{STATE}?ref=main')
    state=json.loads(base64.b64decode(item['content']))
    releases=api('repos/vyos/vyos-nightly-build/releases?per_page=100')
    dry=os.environ.get('DRY_RUN','true').lower()=='true'
    def save():
        payload={'message':'Record Rolling build dispatches','branch':'main','sha':item['sha'],
                 'content':base64.b64encode((json.dumps(state,indent=2)+'\n').encode()).decode()}
        result=json.loads(subprocess.check_output(['gh','api','--method','PUT',f'repos/{REPO}/contents/{STATE}','--input','-'],input=json.dumps(payload),text=True))
        item['sha']=result['content']['sha']
    runs=json.loads(gh('run','list','--repo',REPO,'--workflow','build-board-candidate.yml','--limit','100','--json','displayTitle,databaseId'))
    known={r['displayTitle']:r['databaseId'] for r in runs}
    for release in pending(releases,state):
        tag=release['tag_name']
        record=state.setdefault('releases',{}).setdefault(tag,{'boards':{}})
        missing=[b for b in BOARDS if b not in record['boards']]
        if not missing: continue
        print(f'{tag}: pending boards: {", ".join(missing)}',flush=True)
        if dry: continue
        if 'vyos_commit' not in record:
            # Reference snapshot near the release timestamp, not a package lock.
            cutoff=datetime.strptime(tag,'%Y.%m.%d-%H%M-rolling').strftime('%Y-%m-%dT%H:%M:%SZ')
            commits=api(f'repos/vyos/vyos-build/commits?sha=rolling&until={cutoff}&per_page=1')
            record['vyos_commit']=commits[0]['sha']
            if not re.fullmatch('[0-9a-f]{40}',record['vyos_commit']): raise ValueError('Invalid source SHA')
            save()
        for board in missing:
            run_title=title(board,tag)
            if run_title in known:
                record['boards'][board]={'existing_run':known[run_title]}
            else:
                args=['workflow','run','build-board-candidate.yml','--repo',REPO,'--ref','main']
                inputs={'board':board,'extended_network':'true','tailscale_subnet_router':'false','kvm_over_ip':'false',
                    'expected_update_provider':BOARDS[board],'vyos_ref':record['vyos_commit'],'armbian_ref':ARMBIAN,
                    'rolling_reference':tag,'force_fresh_base':'true','publish_release':'true'}
                for key,val in inputs.items(): args.extend(['-f',f'{key}={val}'])
                gh(*args)
                record['boards'][board]={'dispatched':True}
            save()
            print(f'{tag}: {board} dispatch recorded',flush=True)
    print('Dry run complete' if dry else 'Release check complete')

if __name__=='__main__': main()
