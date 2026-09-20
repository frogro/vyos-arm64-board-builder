#!/usr/bin/env python3
"""Wait for explicit bind addresses from a native VyOS-generated Quadlet file."""
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import sys
import time


def addresses(text):
    result = set()
    for line in text.splitlines():
        if not line.startswith('PublishPort='):
            continue
        value = line.split('=', 1)[1]
        if value.startswith('['):
            host = value.split(']', 1)[0][1:]
        elif value.count(':') >= 2:
            host = value.split(':', 1)[0]
        else:
            continue  # No explicit host address.
        address = ipaddress.ip_address(host)
        if not address.is_unspecified:
            result.add(str(address))
    return result


def main(name):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name):
        raise ValueError('Invalid container name')
    path = Path('/run/containers/systemd') / f'vyos-container-{name}.container'
    required = addresses(path.read_text())
    deadline = time.monotonic() + 60
    previous = None
    while True:
        data = subprocess.check_output(['ip', '-j', 'address', 'show'], text=True, timeout=5)
        present = {str(ipaddress.ip_address(a['local']))
                   for interface in json.loads(data) for a in interface.get('addr_info', [])
                   if a.get('local') and 'tentative' not in a.get('flags', [])
                   and not a.get('tentative', False) and not a.get('dadfailed', False)}
        missing = required - present
        if not missing:
            print('Container bind addresses ready', flush=True)
            return
        if missing != previous:
            print('Waiting for container bind addresses: ' + ', '.join(sorted(missing)), flush=True)
            previous = missing
        if time.monotonic() >= deadline:
            raise TimeoutError('Configured bind addresses are not ready; retry policy applies')
        time.sleep(1)


if __name__ == '__main__':
    try:
        if len(sys.argv) != 2:
            raise ValueError('Expected container name')
        main(sys.argv[1])
    except (ValueError, OSError, TimeoutError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
