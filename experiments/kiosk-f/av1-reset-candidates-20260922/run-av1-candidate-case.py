import runpy,subprocess,pathlib,sys
label=sys.argv[1]
assert label in ('control','identity','tlb','both','identity-domain','tlb-direct')
s=runpy.run_path('/tmp/av1-remote.py')['SSH']
r=pathlib.Path('/mnt/entwicklung/projekte/VyOS/arm/vyos-arm64-board-builder/tmp/av1-reset-candidates-20260922')
p=pathlib.Path('/tmp/av1-'+label+'-test.sh') if label in ('identity-domain','tlb-direct') else r/('test-'+label+'.sh')
d='/config/kiosk-test/av1-reset-candidates-20260922/'+p.name
subprocess.run(s+['sudo -n sh -c '+"'test ! -e "+d+' && cat > '+d+"'"],input=p.read_bytes(),check=True)
with (r/(label+'-transcript.txt')).open('wb') as f:
 q=subprocess.run(s+['sudo -n bash '+d],stdout=f,stderr=subprocess.STDOUT)
print((r/(label+'-transcript.txt')).read_text())
raise SystemExit(q.returncode)
