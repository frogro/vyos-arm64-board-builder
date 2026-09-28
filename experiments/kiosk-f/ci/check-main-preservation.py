#!/usr/bin/env python3
"""Fail a test build if audited main profile behavior or protected inputs drift."""
import itertools
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
