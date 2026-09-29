#!/usr/bin/env python3
"""Fail a test build if audited main profile behavior or protected inputs drift."""
import itertools
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import types

ref = sys.argv[1] if len(sys.argv) > 1 else 'origin/main'
def git(*args):
    return subprocess.check_output(['git', *args], text=True)

baseline = types.ModuleType('baseline_profile')
candidate = types.ModuleType('candidate_profile')
exec(compile(git('show', f'{ref}:tools/feature-profile.py'), 'baseline', 'exec'), baseline.__dict__)
exec(compile(Path('tools/feature-profile.py').read_text(), 'candidate', 'exec'), candidate.__dict__)
for combination in itertools.product((False, True), repeat=3):
    if baseline.derive(*combination) != candidate.derive(*combination):
        raise SystemExit(f'A-D profile behavior differs from {ref}: {combination}')

protected = ['boards', 'profiles', 'patches', 'tools/kvm', 'tools/tailscale',
             '.github/workflows/watch-upstream-rolling.yml']
changed = git('diff', '--name-only', ref, 'HEAD', '--', *protected).strip()
if changed:
    reviewed = 'profiles/kvm-cli/service_kvm-over-ip.xml'
    paths = changed.splitlines()
    if reviewed in paths:
        candidate_xml = Path(reviewed).read_text()
        for name in ('cpu-conversion', 'conversion-fallback'):
            candidate_xml, count = re.subn(r'              <leafNode name="' + name + r'">.*?</leafNode>\n', '', candidate_xml, flags=re.S)
            if count != 1:
                raise SystemExit('Reviewed additive conversion CLI node missing or duplicated')
        if candidate_xml != git('show', f'{ref}:{reviewed}'):
            raise SystemExit('Existing main KVM CLI changed beyond reviewed additive leaves')
        paths.remove(reviewed)
    # Permit only individually reviewed hardware deltas, pinned on both sides.
    # Future main changes and further test-branch edits require a new review.
    delta_file = Path('experiments/profile-g/ci/reviewed-hardware-delta.json')
    if delta_file.exists():
        delta = json.loads(delta_file.read_text())
        if delta.get('schema') != 1:
            raise SystemExit('Unknown reviewed hardware delta schema')
        for path in list(paths):
            approved = delta['files'].get(path)
            if approved is None:
                continue
            result = subprocess.run(['git', 'show', f'{ref}:{path}'], capture_output=True)
            if result.returncode and subprocess.run(['git', 'cat-file', '-e', f'{ref}^{{commit}}'], capture_output=True).returncode:
                raise SystemExit('Cannot resolve baseline commit')
            base_hash = hashlib.sha256(result.stdout).hexdigest() if result.returncode == 0 else None
            candidate_hash = hashlib.sha256(Path(path).read_bytes()).hexdigest()
            if (base_hash, candidate_hash) != (approved['base_sha256'], approved['candidate_sha256']):
                raise SystemExit(f'Reviewed hardware delta drifted: {path}')
            paths.remove(path)
    changed = '\n'.join(paths)
if changed:
    raise SystemExit(f'Protected main files differ; review before building:\n{changed}')
workflow = git('show', f'{ref}:.github/workflows/build-board-candidate.yml')
shared = {s for s in Path('tools/ci/board-build-packages.txt').read_text().splitlines()
          if s and not s.startswith('#')}
if 'tools/ci/board-build-packages.txt' in workflow:
    expected = {s for s in git('show', f'{ref}:tools/ci/board-build-packages.txt').splitlines()
                if s and not s.startswith('#')}
else:
    block = workflow.split('sudo apt-get install -y \\\n', 1)[1].split('\n\n', 1)[0]
    expected = {s.strip().rstrip('\\').strip() for s in block.splitlines()}
if not expected <= shared:
    raise SystemExit(f'Missing main build packages: {sorted(expected-shared)}')
print(f'Main {git("rev-parse", "--short", ref).strip()}: 8 A-D combinations, protected files and {len(expected)} build packages retained')
