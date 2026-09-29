#!/usr/bin/env python3
"""Check the reviewed CLI recipe before starting expensive runtime builds."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('profile', ROOT / 'tools/prepare-vyos-1x-profile.py')
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)
payload = {**profile.PAYLOAD, **profile.TAILSCALE_PAYLOAD}
payload.update({str(p.relative_to(ROOT)): '' for p in (ROOT / 'experiments/kiosk-f/cli').iterdir()
                if p.suffix in ('.py', '.xml')})
actual = profile.recipe(payload)
expected = Path(__file__).with_name('cli-recipe.sha256').read_text().strip()
if actual != expected:
    raise SystemExit(f'CLI recipe changed: expected {expected}, actual {actual}. Review CLI changes and update the pin.')
print('Reviewed CLI recipe verified:', actual)
