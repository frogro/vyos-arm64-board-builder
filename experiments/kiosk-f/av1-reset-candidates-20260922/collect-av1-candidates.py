import runpy,subprocess,pathlib,json,base64,sys
s=runpy.run_path('/tmp/av1-remote.py')['SSH']
r=pathlib.Path('/mnt/entwicklung/projekte/VyOS/arm/vyos-arm64-board-builder/worktrees/kiosk-profile-f/experiments/kiosk-f/av1-reset-candidates-20260922')
script='''import pathlib,json,base64
r=pathlib.Path('/config/kiosk-test/av1-reset-candidates-20260922')
names={'trace.txt','events.txt','pm-state.txt','cmdline-test.txt','test-boot-id.txt','initial-parameters.txt','first-boot-kexec.txt','system-option-kexec-source.txt','kernel.sha256','grubenv-before.txt','grubenv-test.txt','failed-test.txt','defaults-before.cfg','cmdline-before.txt','final-health.txt','pre-return-health.txt','logrotate-startup-collision.txt','logrotate-processes.txt','logrotate-result.txt','hardware.json','decode.log','abort-exit.txt','neighbor.json','neighbor-exit.txt','neighbor.stderr'}
names.update({'hardware-%d.json'%i for i in range(1,4)})
names.update({'decode-%d.log'%i for i in range(1,4)})
print(json.dumps({str(p.relative_to(r)):base64.b64encode(p.read_bytes()).decode() for p in r.rglob('*') if p.is_file() and p.name in names}))
'''
p=subprocess.run(s+['sudo -n python3 -'],input=script.encode(),capture_output=True,check=True)
for n,data in json.loads(p.stdout).items():
 out=r/n;out.parent.mkdir(exist_ok=True,parents=True);out.write_bytes(base64.b64decode(data))
p=subprocess.run(s+['sudo -n journalctl -k -b --no-pager'],capture_output=True,check=True)
(r/('kernel-log-return.txt' if '--final' in sys.argv else 'kernel-log.txt')).write_bytes(p.stdout)
tmp=pathlib.Path('/mnt/entwicklung/projekte/VyOS/arm/vyos-arm64-board-builder/tmp/av1-reset-candidates-20260922')
for p in tmp.glob('*-transcript.txt'):(r/p.name).write_bytes(p.read_bytes())
print('Collected evidence')
