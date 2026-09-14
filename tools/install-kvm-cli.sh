#!/usr/bin/env bash
# Install a complete source-built vyos-1x package. Never merge CLI caches here.
set -euo pipefail
ROOTFS="$(readlink -f "${1:?Usage: $0 <offline-rootfs> <package-artifacts>}")"
ARTIFACTS="$(readlink -f "${2:?KVM package artifact directory required}")"
[[ $EUID -eq 0 && "$ROOTFS" != / && -d "$ROOTFS" ]] || exit 1
for item in dev proc sys run; do
    mountpoint -q "$ROOTFS/$item" || { echo "Missing chroot mount: $item" >&2; exit 1; }
done
python3 - "$ROOTFS" "$ARTIFACTS" <<'PY'
import hashlib, json, shutil, subprocess, sys
from pathlib import Path
root, artifacts = map(Path,sys.argv[1:])
meta=json.loads((artifacts/'build.json').read_text())
assert meta['profiles']==['kvm-over-ip']
name=meta['package']; assert Path(name).name==name and name.endswith('.deb')
package=artifacts/name
assert hashlib.sha256(package.read_bytes()).hexdigest()==meta['package_sha256']
version=subprocess.check_output(['dpkg-query','--admindir='+str(root/'var/lib/dpkg'),'-W','-f=${Version}','vyos-1x'],text=True).strip()
assert version==meta['base_package_version'], 'KVM package does not match this base image'
policy=root/'usr/sbin/policy-rc.d'
assert not policy.is_symlink(), 'Unexpected policy-rc.d symlink'
previous=policy.read_bytes() if policy.exists() else None
mode=policy.stat().st_mode & 0o777 if policy.exists() else None
local=root/'tmp/vyos-1x-kvm.deb'; local.parent.mkdir(exist_ok=True)
assert not local.exists(), 'Unexpected installation staging file'
shutil.copyfile(package,local)
try:
    policy.write_text('#!/bin/sh\nexit 101\n');policy.chmod(0o755)
    subprocess.run(['chroot',str(root),'dpkg','--force-confold','--install','/tmp/vyos-1x-kvm.deb'],check=True)
finally:
    local.unlink(missing_ok=True)
    if previous is None: policy.unlink()
    else: policy.write_bytes(previous);policy.chmod(mode)
code='from vyos.xml_ref import owner; assert owner(["service","kvm-over-ip","local-input","keyboard"], with_tag=True)=="service_kvm_over_ip"'
subprocess.run(['chroot',str(root),'python3','-c',code],check=True)
installed=subprocess.check_output(['chroot',str(root),'dpkg-query','-W','-f=${Version}','vyos-1x'],text=True).strip()
assert installed==meta['package_version']
dest=root/'usr/share/vyos-arm64-board-builder/kvm-cli';dest.mkdir(parents=True,exist_ok=True)
shutil.copy2(artifacts/'build.json',dest/'build.json')
print('Installed source-built vyos-1x KVM profile package:',installed)
PY
