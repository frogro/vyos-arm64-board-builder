#!/usr/bin/env python3
"""Add profile sources before the unmodified upstream generation/build targets."""
import argparse
import importlib.util
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = {
 'tools/kvm-cli/vyos-kvm-mediamtx-supervisor.py': 'src/helpers/vyos-kvm-mediamtx-supervisor.py',
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

def restore_operator_runner_install(source):
    """Restore the former vyos-utils postinst step after its merge into vyos-1x."""
    code = (source/'src/ocaml/vyos_op_run.ml').read_text()
    postinst = source/'debian/vyos-1x.postinst'
    script = postinst.read_text()
    if 'check_command_permissions permissions args;\n    Unix.setuid 0;' not in code:
        raise ValueError('Upstream operator runner changed; permission review required')
    if not script.startswith('#!/bin/bash\n'):
        raise ValueError('Upstream postinst changed; permission review required')
    if 'chmod u+s /usr/bin/vyos-op-run' not in script:
        script = script.replace('#!/bin/bash\n', '#!/bin/bash\n\n'
            '# Restore the upstream vyos-utils operator runner installation.\n'
            '# Native command permissions are checked before setuid.\n'
            'chmod u+s /usr/bin/vyos-op-run || exit 1\n', 1)
    return postinst, script

def remove_duplicate_console_log(source):
    """Keep show/monitor log ownership in their canonical upstream definitions."""
    path = source/'op-mode-definitions/show-console-server.xml.in'
    if not path.exists():
        return None
    text = path.read_text()
    tree = ET.fromstring(text)
    branches = tree.findall("./node[@name='show']/children/node[@name='log']")
    if not branches:
        return None  # Upstream has already removed the duplicate.
    expected = 'journalctl --no-hostname --boot --follow --unit conserver-server.service'
    if len(branches) != 1 or len(branches[0]) != 1:
        raise ValueError('Console log duplicate changed; review required')
    leaves = branches[0].findall('./children/*')
    if (len(leaves) != 1 or leaves[0].get('name') != 'console-server'
            or leaves[0].findtext('command') != expected):
        raise ValueError('Console log duplicate changed; review required')
    for filename, top, command in [
        ('show-log.xml.in', 'show', 'journalctl --no-hostname --boot --unit conserver-server.service'),
        ('monitor-log.xml.in', 'monitor', 'journalctl --no-hostname --follow --boot --unit conserver-server.service')]:
        # Include directives are expanded by the upstream build. This literal
        # console command is outside them; omit directives for this check.
        canonical_text = (path.parent/filename).read_text()
        canonical_text = re.sub(r'(?m)^\s*#include\s+<[^>]+>\s*$', '', canonical_text)
        canonical = ET.fromstring(canonical_text)
        node = canonical.find("./node[@name='%s']/children/node[@name='log']/children/leafNode[@name='console-server']" % top)
        if node is None or node.findtext('command') != command:
            raise ValueError('Canonical console log command changed; review required')
    pattern = r'(?ms)^      <node name="log">.*?^      </node>\n'
    if len(re.findall(pattern, text)) != 1:
        raise ValueError('Console log source layout changed; review required')
    return path, re.sub(pattern, '', text, count=1)

def prepare(source, version, kvm, tailscale=False, kiosk=False):
    if not kvm and not tailscale and not kiosk:
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
    runner_postinst, runner_postinst_text = restore_operator_runner_install(source)
    console_fix = remove_duplicate_console_log(source)
    if kiosk:
        profiles.append('kiosk-f')
    recipe_files = dict(payload)
    if kiosk:
        recipe_files.update({str(p.relative_to(ROOT)): '' for p in
                             (ROOT/'experiments/kiosk-f/cli').iterdir()
                             if p.suffix in ('.py', '.xml')})
    digest = recipe(recipe_files)
    suffix = 'kvm-tailscale' if kvm and tailscale else 'kvm' if kvm else 'tailscale'
    if kiosk:
        suffix = (suffix + '-kiosk') if kvm or tailscale else 'kiosk'
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
    if kiosk:
        spec = importlib.util.spec_from_file_location('kiosk_source', ROOT/'experiments/kiosk-f/cli/prepare-source.py')
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        helper.prepare(source)
    if console_fix:
        console_fix[0].write_text(console_fix[1])
    runner_postinst.write_text(runner_postinst_text)
    rules.write_text(re.sub(pattern, '\tdh_gencontrol -- -v'+output_version, data))
    metadata = {'schema':1, 'profiles':profiles, 'base_package_version':version,
                'package_version':output_version, 'recipe_sha256':digest}
    path=source/'data/arm64-profile-source.json'; path.write_text(json.dumps(metadata,indent=2)+'\n')
    return metadata

if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('source',type=Path); p.add_argument('--version',required=True); p.add_argument('--kvm',action='store_true')
    p.add_argument('--tailscale',action='store_true')
    p.add_argument('--kiosk',action='store_true')
    a=p.parse_args(); print(json.dumps(prepare(a.source,a.version,a.kvm,a.tailscale,a.kiosk)))
