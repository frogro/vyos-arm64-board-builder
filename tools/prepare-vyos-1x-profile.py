#!/usr/bin/env python3
"""Add profile sources before the unmodified upstream generation/build targets."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = {
 'profiles/kvm-cli/service_kvm-over-ip.xml': 'interface-definitions/service_kvm-over-ip.xml.in',
 'tools/kvm-cli/service_kvm_over_ip.py': 'src/conf_mode/service_kvm_over_ip.py',
 'tools/kvm-cli/vyos-kvm-input.py': 'src/helpers/vyos-kvm-input.py',
 'tools/kvm-cli/vyos-kvm-video-supervisor.py': 'src/helpers/vyos-kvm-video-supervisor.py',
 'tools/kvm-cli/vyos-kvm-video-runner': 'src/helpers/vyos-kvm-video-runner.sh',
 'tools/kvm-cli/vyos-kvm-input.service': 'src/systemd/vyos-kvm-input.service',
 'tools/kvm-cli/vyos-kvm-video.service': 'src/systemd/vyos-kvm-video.service',
 'tools/kvm-cli/vyos-kvm-mediamtx.service': 'src/systemd/vyos-kvm-mediamtx.service',
}

def recipe():
    h = hashlib.sha256()
    for name in sorted([*PAYLOAD, 'tools/prepare-vyos-1x-profile.py', 'tools/build-vyos-1x-profile.py']):
        h.update(name.encode()+b'\0'+(ROOT/name).read_bytes()+b'\0')
    return h.hexdigest()

def prepare(source, version, kvm):
    if not kvm:
        return None
    if not re.fullmatch(r'999\.0-\d+-g[0-9a-f]{7,40}', version):
        raise ValueError('Unsupported original vyos-1x version; require an exact clean git-derived version')
    rules = source/'debian/rules'
    data = rules.read_text()
    # Preserve all upstream build, validation, cache generation and packaging targets.
    pattern = r'(?m)^\tdh_gencontrol -- -v[^\n]+$'
    if len(re.findall(pattern, data)) != 1:
        raise ValueError('Upstream package version rule changed; review required')
    digest = recipe()
    output_version = version+'+kvm.'+digest[:12]
    destinations = [source/dst for dst in PAYLOAD.values()]
    if any(p.exists() for p in destinations):
        raise ValueError('Source already contains KVM paths; refusing to overwrite')
    for src,dst in PAYLOAD.items():
        text = (ROOT/src).read_text()
        text = text.replace('/usr/local/libexec/vyos-kvm-video-runner', '/usr/libexec/vyos/vyos-kvm-video-runner.sh')
        text = text.replace('/usr/local/libexec/vyos-kvm-', '/usr/libexec/vyos/vyos-kvm-')
        p = source/dst; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text)
        p.chmod(0o755 if dst.startswith(('src/helpers/', 'src/conf_mode/')) else 0o644)
    rules.write_text(re.sub(pattern, '\tdh_gencontrol -- -v'+output_version, data))
    metadata = {'schema':1, 'profiles':['kvm-over-ip'], 'base_package_version':version,
                'package_version':output_version, 'recipe_sha256':digest}
    path=source/'data/arm64-profile-source.json'; path.write_text(json.dumps(metadata,indent=2)+'\n')
    return metadata

if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('source',type=Path); p.add_argument('--version',required=True); p.add_argument('--kvm',action='store_true')
    a=p.parse_args(); print(json.dumps(prepare(a.source,a.version,a.kvm)))
