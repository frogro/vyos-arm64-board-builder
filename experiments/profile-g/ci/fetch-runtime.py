#!/usr/bin/env python3
"""Consume only a successful, same-commit G runtime; never an older artifact."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
out=Path(sys.argv[1]);sha=os.environ['GITHUB_SHA'];repo=os.environ['GITHUB_REPOSITORY']
def gh(*args):return subprocess.check_output(['gh',*args],text=True)
for attempt in range(90):
    runs=json.loads(gh('api',f'repos/{repo}/actions/runs?head_sha={sha}&per_page=100'))['workflow_runs']
    matches=[r for r in runs if r['path']=='.github/workflows/profile-g-check.yml']
    if matches:
        run=max(matches,key=lambda r:r['id'])
        if run['status']=='completed':
            if run['conclusion']!='success':raise SystemExit('Parallel G runtime failed: '+run['html_url'])
            break
    print('Waiting for same-commit G runtime',sha,flush=True);time.sleep(60)
else:raise SystemExit('G runtime timed out')
out.mkdir(parents=True,exist_ok=False)
subprocess.run(['gh','run','download',str(run['id']),'--repo',repo,'--name',f"profile-g-runtime-arm64-{run['id']}",'--dir',str(out)],check=True)
subprocess.run(['sha256sum','-c','SHA256SUMS'],cwd=out,check=True)
meta=json.loads((out/'runtime.json').read_text())
assert meta['source_commit']==sha and meta['profile']=='receiver-g',meta
inspect=json.loads((out/'image.json').read_text())[0]
assert inspect['Architecture']=='arm64'
assert meta['tag'] in inspect['RepoTags']
assert inspect['Config']['Labels']['io.vyarm.receiver.version']=='1'
(out/'source-run.txt').write_text(str(run['id'])+'\n')
print('Verified matching G runtime:',run['html_url'])
