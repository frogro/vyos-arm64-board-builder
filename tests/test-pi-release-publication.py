#!/usr/bin/env python3
"""Exercise Pi publication without contacting GitHub, including checksum failure."""
import hashlib,json,os,subprocess,tempfile
from pathlib import Path
repo=Path(__file__).resolve().parents[1]
os.chdir(repo)
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'selection').mkdir();(p/'bin').mkdir()
 (p/'release.env').write_text('RELEASE_BASENAME=pi-test\nRELEASE_TAG=pi-test\nVYOS_VERSION=999.test\n')
 (p/'selection/feature-profiles.env').write_text('BUILD_PROFILE=network\n')
 (p/'board-manifest.json').write_text(json.dumps(dict(board='raspberry-pi-5',profile='network',architecture='arm64',update_provider='firmware-files')))
 for suffix in ('iso','img.xz'):
  f=p/('pi-test.'+suffix);f.write_bytes(b'fixture');Path(str(f)+'.sha256').write_text(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n')
 (p/'bin/gh').write_text('#!/bin/sh\nprintf "%s\\n" "$@" >> "$GH_CALLS"\n');(p/'bin/gh').chmod(0o755)
 env={**os.environ,'PATH':str(p/'bin')+':'+os.environ['PATH'],'GH_CALLS':str(p/'calls')}
 subprocess.run(['bash','tools/publish-board-release.sh','raspberry-pi-5',str(p)],env=env,check=True)
 feed=json.loads((p/'image-version.json').read_text());assert feed[0]['url'].endswith('/pi-test/pi-test.iso')
 calls=(p/'calls').read_text();assert str(p/'image-version.json') in calls and str(p/'pi-test.iso') in calls and '--draft=false' in calls
 (p/'calls').unlink();(p/'pi-test.iso').write_bytes(b'corrupt')
 result=subprocess.run(['bash','tools/publish-board-release.sh','raspberry-pi-5',str(p)],env=env,capture_output=True)
 assert result.returncode and not (p/'calls').exists()
 print('PASS: Pi publishes image, ISO and feed; corrupt ISO prevents publication')
