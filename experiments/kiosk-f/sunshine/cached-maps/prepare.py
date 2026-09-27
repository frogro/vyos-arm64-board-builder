#!/usr/bin/env python3
"""Create an isolated Panthor cache experiment; never patch the supplied source."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('baseline', type=Path)
parser.add_argument('destination', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parent
baseline = args.baseline.resolve(strict=True)
destination = args.destination.resolve()
if destination.exists() or destination == baseline or baseline in destination.parents:
    parser.error('destination must be new and outside the baseline source')
manifest = json.loads((root / 'baseline-files.json').read_text())
for name, checksums in manifest.items():
    if hashlib.sha256((baseline / name).read_bytes()).hexdigest() != checksums['before']:
        parser.error(f'baseline differs: {name}; audit this kernel before applying')
subprocess.run(['cp', '-a', '--reflink=auto', str(baseline), str(destination)], check=True)
subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i',
                str(root / 'panthor-6.18.50-backport.patch')], cwd=destination, check=True)
for name, checksums in manifest.items():
    if hashlib.sha256((destination / name).read_bytes()).hexdigest() != checksums['after']:
        raise SystemExit(f'patched file differs: {name}')
print(f'Prepared and verified: {destination}')
