#!/usr/bin/env python3
"""Run inside target rootfs: seed native VyOS serial config, not a parallel getty."""
import argparse
from pathlib import Path
import re
from vyos.configtree import ConfigTree

parser = argparse.ArgumentParser()
parser.add_argument('device')
parser.add_argument('baud')
parser.add_argument('paths', nargs='+')
a = parser.parse_args()
if not re.fullmatch(r'tty(?:S|AMA)\d+', a.device) or not a.baud.isdigit():
    raise SystemExit('Invalid board console')
for filename in a.paths:
    path = Path(filename)
    config = ConfigTree(path.read_text())
    # These are initial-image defaults, never a running user's configuration.
    if config.exists(['system', 'console']):
        config.delete(['system', 'console'])
    config.set(['system', 'console', 'device', a.device, 'speed'], value=a.baud)
    config.set(['system', 'console', 'device', a.device, 'kernel'])
    config.set_tag(['system', 'console', 'device'])
    path.write_text(config.to_string())
