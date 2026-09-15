#!/usr/bin/env python3
"""Build a profile-specific vyos-1x package matching the actual raw image package.

Runs only on the image builder, never on a deployed router. No package cache
reuse: every output directory has isolated source and explicit provenance.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('profile_source',HERE/'prepare-vyos-1x-profile.py')
profile=importlib.util.module_from_spec(spec); spec.loader.exec_module(profile)

def run(*args,**kw):
    return subprocess.run(list(map(str,args)),check=True,**kw)

def output(*args):
    return subprocess.check_output(list(map(str,args)),text=True).strip()

def resolve(version):
    m=re.fullmatch(r'999\.0-\d+-g([0-9a-f]{7,40})',version)
    if not m: raise ValueError('Cannot match installed vyos-1x version to an exact public source commit: '+version)
    request=urllib.request.Request('https://api.github.com/repos/vyos/vyos-1x/commits/'+m[1],headers={'User-Agent':'vyos-arm64-board-builder'})
    with urllib.request.urlopen(request,timeout=60) as r: sha=json.load(r)['sha']
    if not re.fullmatch('[0-9a-f]{40}',sha) or not sha.startswith(m[1]): raise ValueError('Source commit mismatch')
    return sha

def version_from_root(root):
    if root==Path('/') or not (root/'var/lib/dpkg/status').is_file(): raise ValueError('Expected an offline image rootfs')
    return output('dpkg-query','--admindir='+str(root/'var/lib/dpkg'),'-W','-f=${Version}','vyos-1x')

def build_container(out):
    override=os.environ.get('VYOS_1X_BUILD_IMAGE')
    if override:
        run('docker','pull','--platform','linux/arm64',override)
        image=override
        provenance={'image_override':override}
    else:
        # Docker Hub's vyos/vyos-build:rolling is AMD64-only. Build ARM64 from
        # the official Dockerfile rather than relabeling that binary image.
        ref=os.environ.get('VYOS_1X_CONTAINER_REF','rolling')
        if not re.fullmatch(r'[A-Za-z0-9._/-]+',ref): raise ValueError('Invalid container source ref')
        req=urllib.request.Request('https://api.github.com/repos/vyos/vyos-build/commits/'+ref,headers={'User-Agent':'vyos-arm64-board-builder'})
        with urllib.request.urlopen(req,timeout=60) as response: commit=json.load(response)['sha']
        if not re.fullmatch('[0-9a-f]{40}',commit): raise ValueError('Invalid container source commit')
        context=out/'container-source'
        run('git','init',context)
        run('git','-C',context,'remote','add','origin','https://github.com/vyos/vyos-build.git')
        run('git','-C',context,'fetch','--depth=1','origin',commit)
        run('git','-C',context,'checkout','--detach','FETCH_HEAD')
        image='vyos-profile-build:arm64-'+commit[:12]
        run('docker','build','--network','host','--platform','linux/arm64',
            '--build-arg','ARCH=arm64v8/','-t',image,context/'docker')
        provenance={'container_source_commit':commit}
    arch=output('docker','image','inspect','--format={{.Architecture}}',image)
    if arch!='arm64': raise ValueError('Refusing non-ARM64 build container: '+arch)
    return output('docker','image','inspect','--format={{.Id}}',image),provenance

def build(version,out,kvm=True,tailscale=False):
    if not kvm and not tailscale:
        raise ValueError('Select at least one native CLI profile')
    host_arch=output('uname','-m')
    if host_arch!='aarch64' and os.environ.get('VYOS_1X_ALLOW_EMULATION')!='yes':
        raise ValueError('Use a native ARM64 runner or explicitly provision ARM64 binfmt and enable VYOS_1X_ALLOW_EMULATION=yes')
    sha=resolve(version)
    if out.exists(): raise ValueError('Artifact directory already exists; use a fresh build directory')
    out.mkdir(parents=True)
    image_id,container_provenance=build_container(out)
    with tempfile.TemporaryDirectory(prefix='vyos-1x-profile-',dir=out.parent) as tmp:
        work=Path(tmp); source=work/'vyos-1x'
        run('git','init',source)
        run('git','-C',source,'remote','add','origin','https://github.com/vyos/vyos-1x.git')
        run('git','-C',source,'fetch','--depth=1','origin',sha)
        run('git','-C',source,'checkout','--detach','FETCH_HEAD')
        if output('git','-C',source,'rev-parse','HEAD')!=sha: raise ValueError('Checkout mismatch')
        run('git','-C',source,'submodule','update','--init','--recursive','--depth=1')
        metadata=profile.prepare(source,version,kvm,tailscale)
        # Upstream lint uses git ls-files: include the added files in its scope.
        run('git','-C',source,'add','.')
        run('docker','run','--rm','--privileged','--network','host','--platform','linux/arm64',
            '-v',str(work)+':/work','-w','/work/vyos-1x','--entrypoint','/bin/bash',image_id,
            '-lc','git config --global --add safe.directory /work/vyos-1x; dpkg-buildpackage -b -us -uc')
        packages=list(work.glob('vyos-1x_*.deb'))
        if len(packages)!=1: raise ValueError('Expected exactly one vyos-1x binary package')
        package=packages[0]
        # Preserve the completed binary if post-build validation fails.
        # Only build.json/SHA256SUMS at the artifact root mark validated output.
        unverified=out/'unverified';unverified.mkdir()
        shutil.copy2(package,unverified/package.name)
        if output('dpkg-deb','-f',package,'Version')!=metadata['package_version']: raise ValueError('Built package version mismatch')
        if output('dpkg-deb','-f',package,'Architecture')!='arm64': raise ValueError('Built package architecture mismatch')
        unpack=work/'verify';run('dpkg-deb','-x',package,unpack)
        required=['usr/share/vyos/reftree.cache','usr/lib/python3/dist-packages/vyos/xml_ref/update_cache.py']
        owners=[]
        if kvm:
            required += ['opt/vyatta/share/vyatta-cfg/templates/service/kvm-over-ip/local-input/keyboard/node.def',
                         'usr/libexec/vyos/conf_mode/service_kvm_over_ip.py',
                         'usr/libexec/vyos/vyos-kvm-input.py','lib/systemd/system/vyos-kvm-input.service']
            owners.append('service_kvm_over_ip.py')
        if tailscale:
            required += ['opt/vyatta/share/vyatta-cfg/templates/service/tailscale/advertise-route/node.def',
                         'usr/libexec/vyos/conf_mode/service_tailscale.py',
                         'usr/libexec/vyos/vyos-tailscale-apply.py']
            owners.append('service_tailscale.py')
        for rel in required:
            if not (unpack/rel).is_file(): raise ValueError('Generated package file missing: '+rel)
        includes=json.loads((unpack/'usr/share/vyos/configd-include.json').read_text())
        for owner in owners:
            if owner not in includes: raise ValueError('Native configd include generation omitted '+owner)
        dest=out/package.name;shutil.copy2(package,dest)
        metadata.update(container_provenance)
        metadata.update(source_commit=sha,build_container_id=image_id,build_host_arch=host_arch,package=dest.name,
                        package_sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
        (out/'build.json').write_text(json.dumps(metadata,indent=2)+'\n')
        (out/'SHA256SUMS').write_text(metadata['package_sha256']+'  '+dest.name+'\n')
    return metadata

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('rootfs',type=Path);p.add_argument('artifacts',type=Path)
    p.add_argument('--kvm',choices=['yes','no'],default='yes')
    p.add_argument('--tailscale',choices=['yes','no'],default='no')
    a=p.parse_args();build(version_from_root(a.rootfs.resolve()),a.artifacts.resolve(),a.kvm=='yes',a.tailscale=='yes')
