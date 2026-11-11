#!/usr/bin/env python3
"""Kernel ABI identity from the selected VyOS source, including its revision."""
import argparse
from pathlib import Path
import re
import tomllib


def kernel_release(defaults):
    version, flavor = defaults['kernel_version'], defaults['kernel_flavor']
    if not isinstance(version, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version):
        raise ValueError('Unsupported VyOS kernel version')
    if not isinstance(flavor, str) or not re.fullmatch(r'[a-z0-9-]+', flavor):
        raise ValueError('Unsupported VyOS kernel flavor')
    # Missing means the pre-revision ABI. Present but invalid must never
    # silently select the old package/module tree.
    suffix = flavor
    if 'kernel_revision' in defaults:
        revision = defaults['kernel_revision']
        if type(revision) not in (str, int) or not re.fullmatch(r'[1-9][0-9]*', str(revision)):
            raise ValueError('Unsupported VyOS kernel revision')
        suffix = f'{revision}-{flavor}'
    return f'{version}-{suffix}'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--localversion', action='store_true')
    parser.add_argument('--flavor', default='')
    args = parser.parse_args()
    defaults = tomllib.loads((args.source/'data/defaults.toml').read_text())
    if args.flavor:
        defaults['kernel_flavor'] = args.flavor
    release = kernel_release(defaults)
    print(release[len(defaults['kernel_version']):] if args.localversion else release)
