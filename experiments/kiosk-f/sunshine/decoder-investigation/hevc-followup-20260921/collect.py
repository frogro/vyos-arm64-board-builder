import json,pathlib,re,hashlib
root=pathlib.Path('/config/kiosk-test/kernel-test3/hevc-followup-20260921')
rows=[]
for p in sorted(root.glob('*run-*/*.json')):
 if not p.stat().st_size:continue
 d=json.loads(p.read_text()); props={}
 for event in d.get('mediaEvents',[]):
  for prop in event.get('params',{}).get('properties',[]):props[prop['name']]=prop['value']
 stderr=p.with_suffix('.stderr').read_text()
 rows.append({'run':p.parent.name,'final_frame_sha256':hashlib.sha256(d.get('finalFramePNG','').encode()).hexdigest(),'page':{k:v for k,v in d['page'].items() if k!='frames'},'decoder':props.get('kVideoDecoderName'),'hardware':props.get('kIsPlatformVideoDecoder'),'videoTracks':props.get('kVideoTracks'),'allocations':re.findall(r'VYARM_CAPTURE[^\n]+',stderr),'temperatures_before':p.with_name('1-hevc-temperature-before.txt').read_text().splitlines(),'temperatures_after':p.with_name('1-hevc-temperature-after.txt').read_text().splitlines() if p.with_name('1-hevc-temperature-after.txt').exists() else []})
print(json.dumps(rows,indent=2))
