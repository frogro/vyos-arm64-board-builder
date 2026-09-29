#!/usr/bin/env python3
"""Poll official releases and track build outcomes and bounded retries on the default branch."""
import base64
import json
import os
import re
import subprocess
from datetime import datetime

REPO = 'frogro/vyos-arm64-board-builder'
STATE = '.github/rolling-build-state.json'
BOARDS = {'radxa-e52c':'uboot-extlinux', 'rock-5b':'efi-firmware-dtb', 'raspberry-pi-5':'firmware-files', 'orangepi5-plus':'efi-firmware-dtb'}
# Do not backfill old releases when enrolling an additional board.
BOARD_FIRST_ROLLING = {'orangepi5-plus': '2026.09.28-0746-rolling'}
MAX_ATTEMPTS = 3  # Initial build plus at most two failed-job reruns.

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

def retry_action(entry, run, latest=True):
    """Decide without changing GitHub; never restart active or successful work."""
    if run['status'] != 'completed': return 'waiting'
    if run['conclusion'] == 'success': return 'success'
    if entry.get('retry_disabled') or not latest: return 'suppressed'
    if run['conclusion'] not in ('failure', 'timed_out'): return 'attention'
    attempt = run['run_attempt']
    if entry.get('retry_request_error_for_attempt') == attempt: return 'attention'
    if attempt >= MAX_ATTEMPTS: return 'exhausted'
    if entry.get('retry_requested_for_attempt', 0) >= attempt: return 'waiting'
    return 'retry'


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
    known={}
    for run in runs:  # gh returns newest first; retain the newest matching run.
        known.setdefault(run['displayTitle'], run['databaseId'])
    selected=pending(releases,state)
    problems=[]
    for release in selected:
        tag=release['tag_name']
        record=state.setdefault('releases',{}).setdefault(tag,{'boards':{}})
        for board, entry in record['boards'].items():
            run_id=entry.get('run_id') or entry.get('existing_run') or known.get(title(board,tag))
            if not run_id:
                print(f'{tag}: {board}: awaiting run discovery',flush=True)
                continue  # Never duplicate a dispatch just because indexing is delayed.
            run=api(f'repos/{REPO}/actions/runs/{run_id}')
            action=retry_action(entry,run,tag==selected[-1]['tag_name'])
            print(f'{tag}: {board}: {run["status"]}/{run["conclusion"]}, {action}',flush=True)
            if dry: continue
            before=dict(entry)
            entry.update(run_id=run_id, status=run['status'], conclusion=run['conclusion'],
                         run_attempt=run['run_attempt'])
            if entry != before: save()
            if action == 'retry':
                # Record intent first so delayed API status cannot trigger duplicate reruns.
                entry['retry_requested_for_attempt']=run['run_attempt']
                save()
                try:
                    gh('run','rerun',str(run_id),'--failed','--repo',REPO)
                except subprocess.CalledProcessError:
                    # Keep the reserved attempt on an uncertain response: fail visibly
                    # instead of risking an unbounded rerun loop.
                    entry['retry_request_error_for_attempt']=run['run_attempt']
                    save()
                    raise SystemExit(f'Rerun request failed or uncertain: {run_id}; inspect manually')
            elif action in ('exhausted','attention'):
                problems.append(f'{tag}/{board}: {action} ({run["html_url"]})')
        missing=[b for b in BOARDS if b not in record['boards']
                 and tag >= BOARD_FIRST_ROLLING.get(b, '')]
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
    if problems:
        raise SystemExit('Builds require attention: ' + '; '.join(problems))
    print('Dry run complete' if dry else 'Release check complete')

if __name__=='__main__': main()
