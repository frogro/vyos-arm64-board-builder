#!/bin/bash
set -euo pipefail
cd /home/photobooth/vyarm-board-build-20260922
exec > >(tee -a wayland-complete-build.log) 2>&1
D=(docker -H unix:///run/vyarm-nuc-docker.sock)
[[ $(cat /home/photobooth/wayland-cli-inputs/status) == complete ]]
mkdir -p wayland-artifacts-20260923
"${D[@]}" save localhost/vyarm-kiosk:wayland-corrected-20260923 -o "$PWD/wayland-artifacts-20260923/runtime.tar"
"${D[@]}" image inspect localhost/vyarm-kiosk:wayland-corrected-20260923 --format '{{.Id}}' > wayland-artifacts-20260923/image-id
python3 - <<'PY'
from pathlib import Path
import json, hashlib, subprocess
p=Path('wayland-artifacts-20260923')
m=json.loads(Path('runtime-artifacts/runtime.json').read_text())
m.update(image='localhost/vyarm-kiosk:wayland-corrected-20260923',image_id=(p/'image-id').read_text().strip(),builder_commit='934a8de',wayland_drm='weston14')
with (p/'runtime.tar').open('rb') as f: m['archive_sha256']=hashlib.file_digest(f,'sha256').hexdigest()
(p/'runtime.json').write_text(json.dumps(m,indent=2)+'\n')
c=Path('/home/photobooth/wayland-cli-inputs/output')
deb,=c.glob('*.deb')
b=json.loads(Path('cli-artifacts/build.json').read_text())
b['base_package_version']=b['package_version']
b.update(package=deb.name,package_sha256=hashlib.sha256(deb.read_bytes()).hexdigest(),package_version=subprocess.check_output(['dpkg-deb','-f',str(deb),'Version'],text=True).strip(),builder_commit='934a8de',generation='incremental source generators; unchanged compiled binaries retained')
(c/'build.json').write_text(json.dumps(b,indent=2)+'\n')
PY
"${D[@]}" run --rm --privileged -v /dev:/dev --name vyarm-wayland-image-20260923 -v "$PWD:/work" -v /home/photobooth/wayland-cli-inputs:/cli vyarm-image-pack:20260922 bash /work/repack-inputs-20260923/repack-wayland.sh
