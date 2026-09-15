#!/usr/bin/env python3
"""Add profile sources before the unmodified upstream generation/build targets."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = {
 'profiles/kvm-cli/show_kvm-over-ip.xml': 'op-mode-definitions/show_kvm-over-ip.xml.in',
 'tools/kvm-cli/kvm_capture_status.py': 'src/op_mode/kvm_capture_status.py',
 'profiles/kvm-cli/service_kvm-over-ip.xml': 'interface-definitions/service_kvm-over-ip.xml.in',
 'tools/kvm-cli/service_kvm_over_ip.py': 'src/conf_mode/service_kvm_over_ip.py',
 'tools/kvm-cli/vyos-kvm-input.py': 'src/helpers/vyos-kvm-input.py',
 'tools/kvm-cli/vyos-kvm-capture.py': 'src/helpers/vyos-kvm-capture.py',
 'tools/kvm-cli/vyos-kvm-video-supervisor.py': 'src/helpers/vyos-kvm-video-supervisor.py',
 'tools/kvm-cli/vyos-kvm-video-runner': 'src/helpers/vyos-kvm-video-runner.sh',
 'tools/kvm-cli/vyos-kvm-input.service': 'src/systemd/vyos-kvm-input.service',
 'tools/kvm-cli/vyos-kvm-video.service': 'src/systemd/vyos-kvm-video.service',
 'tools/kvm-cli/vyos-kvm-mediamtx.service': 'src/systemd/vyos-kvm-mediamtx.service',
}

TAILSCALE_PAYLOAD = {
 'profiles/tailscale-cli/service_tailscale.xml': 'interface-definitions/service_tailscale.xml.in',
 'profiles/tailscale-cli/show_tailscale.xml': 'op-mode-definitions/show_tailscale.xml.in',
 'profiles/tailscale-cli/request_tailscale.xml': 'op-mode-definitions/request_tailscale.xml.in',
 'tools/tailscale-cli/service_tailscale.py': 'src/conf_mode/service_tailscale.py',
 'tools/tailscale-cli/vyos-tailscale-apply.py': 'src/helpers/vyos-tailscale-apply.py',
 'tools/common-firstboot/vyos-arm64-tailscaled.service': 'src/systemd/vyos-arm64-tailscaled.service',
}

def recipe(payload=None):
    if payload is None:
        payload = PAYLOAD
    h = hashlib.sha256()
    for name in sorted([*payload, 'tools/prepare-vyos-1x-profile.py', 'tools/build-vyos-1x-profile.py']):
        h.update(name.encode()+b'\0'+(ROOT/name).read_bytes()+b'\0')
    return h.hexdigest()

def prepare(source, version, kvm, tailscale=False):
    if not kvm and not tailscale:
        return None
    payload = {}
    profiles = []
    if kvm:
        payload.update(PAYLOAD)
        profiles.append('kvm-over-ip')
    if tailscale:
        payload.update(TAILSCALE_PAYLOAD)
        profiles.append('tailscale-subnet-router')
    if not re.fullmatch(r'999\.0-\d+-g[0-9a-f]{7,40}', version):
        raise ValueError('Unsupported original vyos-1x version; require an exact clean git-derived version')
    rules = source/'debian/rules'
    data = rules.read_text()
    # Preserve all upstream build, validation, cache generation and packaging targets.
    pattern = r'(?m)^\tdh_gencontrol -- -v[^\n]+$'
    if len(re.findall(pattern, data)) != 1:
        raise ValueError('Upstream package version rule changed; review required')
    digest = recipe(payload)
    suffix = 'kvm-tailscale' if kvm and tailscale else 'kvm' if kvm else 'tailscale'
    output_version = version+'+'+suffix+'.'+digest[:12]
    destinations = [source/dst for dst in payload.values()]
    if any(p.exists() for p in destinations):
        raise ValueError('Source already contains selected profile paths; refusing to overwrite')
    for src,dst in payload.items():
        text = (ROOT/src).read_text()
        text = text.replace('/usr/local/libexec/vyos-kvm-video-runner', '/usr/libexec/vyos/vyos-kvm-video-runner.sh')
        text = text.replace('/usr/local/libexec/vyos-kvm-', '/usr/libexec/vyos/vyos-kvm-')
        p = source/dst; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text)
        p.chmod(0o755 if dst.startswith(('src/helpers/', 'src/conf_mode/', 'src/op_mode/')) else 0o644)
    rules.write_text(re.sub(pattern, '\tdh_gencontrol -- -v'+output_version, data))
    metadata = {'schema':1, 'profiles':profiles, 'base_package_version':version,
                'package_version':output_version, 'recipe_sha256':digest}
    path=source/'data/arm64-profile-source.json'; path.write_text(json.dumps(metadata,indent=2)+'\n')
    return metadata

if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('source',type=Path); p.add_argument('--version',required=True); p.add_argument('--kvm',action='store_true')
    p.add_argument('--tailscale',action='store_true')
    a=p.parse_args(); print(json.dumps(prepare(a.source,a.version,a.kvm,a.tailscale)))
