#!/usr/bin/env python3
"""Run the selected upstream recipe while retaining kernel build objects."""
from pathlib import Path
import re
import subprocess
import sys

PACKAGES = ('linux-kernel', 'nat-rtsp', 'jool', 'realtek-r8126',
            'realtek-r8152', 'ipt-netflow')


def retention_args(help_text):
    options = set(re.findall(r'(?<![\w-])--[a-z][a-z-]*', help_text))
    if '--dont-keep-kernel' in options:
        return []  # Current upstream retains the tree by default.
    if '--keep-kernel' in options:
        return ['--keep-kernel']
    raise ValueError('Unknown upstream kernel retention options; refusing to guess')


def main():
    recipe = Path('build.py')
    help_text = subprocess.check_output([sys.executable, str(recipe), '--help'], text=True)
    command = [sys.executable, str(recipe), '--packages', *PACKAGES, *retention_args(help_text)]
    print('Running upstream kernel recipe:', ' '.join(command), flush=True)
    subprocess.run(command, check=True)


if __name__ == '__main__':
    main()
