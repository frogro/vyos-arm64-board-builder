#!/usr/bin/env python3
"""Publish verified combined-profile artifacts without rebuilding images."""
import hashlib,json,subprocess,sys,tarfile,tempfile,re,time
from pathlib import Path
board,run,sha,root=sys.argv[1:];root=Path(root);candidate=root/f'vyos-{board}-current-candidate';repo='frogro/vyos-arm64-board-builder'
assert board in ('rock-5b','orangepi5-plus','raspberry-pi-5','radxa-e52c') and run.isdigit() and re.fullmatch(r'[0-9a-f]{40}',sha)
source=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{run}'],text=True))
assert source['conclusion']=='success' and source['head_sha']==sha
release_env=dict(line.split('=',1) for line in (candidate/'release.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
import shlex
version=shlex.split(release_env['VYOS_VERSION'])[0]
base_tag=shlex.split(release_env['RELEASE_TAG'])[0]
tag=base_tag+'-run-'+run
# Retain the already prepared release tags for these two source builds.
if run in ('36642095198','36644090408'):
 tag=f'2026.09.28-1945-selfbuilt-{board}-adfg-run-{run}'
img=next(candidate.glob('*.img.xz'));iso=next(candidate.glob('*.iso'))
for f in (img,iso):
 with f.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
 assert digest==Path(str(f)+'.sha256').read_text().split()[0],f
manifest=json.loads((candidate/'board-manifest.json').read_text())
assert manifest['board']==board
provider={'rock-5b':'efi-firmware-dtb','orangepi5-plus':'efi-firmware-dtb','raspberry-pi-5':'firmware-files','radxa-e52c':'uboot-extlinux'}[board]
assert manifest['update_provider']==provider
features=manifest['features']
assert features['extended_network'] and features['tailscale_subnet_router']
full=board!='radxa-e52c'
assert all(bool(features.get(key,False))==full for key in ('kvm_over_ip','kiosk_f','receiver_g'))
profiles='A–D/F/G' if full else 'A–C'
chunk=1500*1024*1024
parts=[f'{img.name}.part{n:02d}' for n in range(1,(img.stat().st_size+chunk-1)//chunk+1)] if img.stat().st_size>=2147483648 else []
assert iso.stat().st_size<2147483648, 'ISO exceeds GitHub limit; cannot publish a directly downloadable update ISO'
installation=(f"Download all {len(parts)} parts and join them before flashing." if parts else f"Flash `{img.name}` directly.")
joining=('\nReassemble on Linux/macOS:\n```sh\ncat '+ ' '.join(parts)+' > '+img.name+'\nsha256sum -c '+img.name+'.sha256\n```\nWindows Command Prompt:\n```bat\ncopy /b '+'+'.join(parts)+' '+img.name+'\ncertutil -hashfile '+img.name+' SHA256\n```\nDo not flash individual parts. Joining restores the original image byte for byte.\n') if parts else ''
with tempfile.TemporaryDirectory(prefix='adfg-publish-') as work:
 w=Path(work);notes=w/'notes.md'
 notes.write_text(f"""VyOS {version} for {board}, profiles {profiles}.

- System-image update: `{iso.name}` and its SHA-256 checksum.
- SD/eMMC installation: {installation}
- Board-specific update provider: `{provider}`.
- Includes extended networking and Tailscale.{" Also includes KVM, Chromium kiosk and receiver software." if full else " E52C excludes KVM, kiosk and receivers."}
{joining}
[Source build](https://github.com/{repo}/actions/runs/{run}); builder commit `{sha}`.

IMG and ISO checksums verified before publication. Includes board manifest and build provenance. This test release is separate from the public A/B update channels. Hardware validation remains outstanding; retain the previous working image when installing.
""")
 releases=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/releases?per_page=100'],text=True))
 existing=next((r for r in releases if r['tag_name']==tag),None)
 if existing:
  assert existing['draft'], 'Refuse to modify a published release'
  subprocess.run(['gh','release','edit',tag,'-R',repo,'--notes-file',str(notes)],check=True)
 else:
  subprocess.run(['gh','release','create',tag,'-R',repo,'--target',sha,'--draft','--prerelease','--title',f'VyOS {version} {board} {profiles}','--notes-file',str(notes)],check=True)
 provenance=w/'build-provenance.json';provenance.write_text(json.dumps({'board':board,'run':int(run),'commit':sha,'profile':manifest['profile']},indent=2)+'\n')
 report=w/f'build-report-{run}.tar.gz'
 with tarfile.open(report,'w:gz') as t:
  for p in root.glob('*build-report*'):t.add(p,arcname=p.name)
  for name in ('selection','boot','artifacts','release.env'):
   p=candidate/name
   if p.exists():t.add(p,arcname=name)
 def upload(f):
  for attempt in range(4):
   result=subprocess.run(['gh','release','upload',tag,'-R',repo,str(f),'--clobber'])
   if result.returncode==0:break
   if attempt==3:raise RuntimeError('Upload failed: '+f.name)
   time.sleep(5*(attempt+1))
  print('UPLOADED',f.name,flush=True)
 assets=[iso,Path(str(iso)+'.sha256'),Path(str(img)+'.sha256'),candidate/'board-manifest.json',provenance,report]
 expected={}
 for f in assets:
  with f.open('rb') as st:expected[f.name]=hashlib.file_digest(st,'sha256').hexdigest()
  upload(f)
 if not parts:
  with img.open('rb') as st:expected[img.name]=hashlib.file_digest(st,'sha256').hexdigest()
  upload(img)
 else:
  with img.open('rb') as st:
   for name in parts:
    part=w/name;remaining=chunk;h=hashlib.sha256()
    with part.open('wb') as out:
     while remaining:
      data=st.read(min(8*1024*1024,remaining))
      if not data:break
      out.write(data);h.update(data);remaining-=len(data)
    assert part.stat().st_size>0
    expected[part.name]=h.hexdigest();upload(part);part.unlink()
   assert not st.read(1)
 sums=w/'SHA256SUMS';sums.write_text(''.join(f'{h}  {n}\n' for n,h in expected.items()));upload(sums)
 remote=next(r for r in json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/releases?per_page=100'],text=True)) if r['tag_name']==tag)
 for a in remote['assets']:
  if a['name'] in expected:assert a['state']=='uploaded' and a['digest']=='sha256:'+expected.pop(a['name']),a['name']
 assert not expected,expected
 subprocess.run(['gh','release','edit',tag,'-R',repo,'--draft=false','--latest=false'],check=True)
 print('PUBLISHED https://github.com/'+repo+'/releases/tag/'+tag,flush=True)
