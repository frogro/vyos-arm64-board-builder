#!/usr/bin/env python3
"""Check G's native configd contract before building receiver/image artifacts."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[3]
UPSTREAM = '4e3e38a2e665bb2d8e9446116e02300bb38a2ab4'
spec = importlib.util.spec_from_file_location('profile', ROOT/'tools/prepare-vyos-1x-profile.py')
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)
with tempfile.TemporaryDirectory(prefix='adfg-native-cli-') as tmp:
    source = Path(tmp)
    def git(*args):
        subprocess.run(['git', '-C', str(source), *args], check=True)
    git('init', '--quiet')
    git('fetch', '--depth', '1', 'https://github.com/vyos/vyos-1x.git', UPSTREAM)
    git('checkout', '--quiet', '--detach', 'FETCH_HEAD')
    # Check the cumulative images and standalone F/G against real upstream source.
    selections = [(False, True, False, False), (True, True, False, False),
                  (False, False, True, False), (False, False, False, True),
                  (False, False, True, True), (True, True, True, False),
                  (True, True, True, True),
                  (False, False, False, False, True),
                  (False, False, False, True, True)]
    for selected in selections:
        git('reset', '--hard', '--quiet', UPSTREAM)
        git('clean', '-fdx', '--quiet')
        metadata = profile.prepare(source, '999.0-14942-g4e3e38a2e', *selected)
        if selected == (True, True, True, True):
            expected = Path(__file__).with_name('cli-recipe.sha256').read_text().strip()
            if metadata['recipe_sha256'] != expected:
                raise SystemExit(f'G CLI recipe mismatch: {metadata}')
        for enabled, module in [(selected[2], 'kiosk'), (selected[3], 'receiver')]:
            assert (source / f'python/vyos/{module}.py').exists() == enabled
        subprocess.run([sys.executable, 'scripts/generate-configd-include-json.py'], cwd=source, check=True)
        subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'src/tests',
                        '-p', 'test_configd_inspect.py', '-v'], cwd=source, check=True)
        print('Native CLI combination verified:', selected)
    print('All selected native configd contracts and full CLI recipe verified')
