#!/usr/bin/env python3
"""Apply only CLI-owned preferences. Never authenticate or reset node state."""
import json
from pathlib import Path
import subprocess
import sys

CONFIG = Path('/run/vyos-tailscale/config.json')
BINARY = '/config/tailscale/bin/tailscale'
SOCKET = '/run/tailscale/tailscaled.sock'


def arguments(config):
    return [BINARY, '--socket=' + SOCKET, 'set',
            '--advertise-routes=' + ','.join(config['advertise_routes']),
            '--accept-routes=' + str(config['accept_routes']).lower(),
            '--snat-subnet-routes=' + str(config['snat_subnet_routes']).lower(),
            '--netfilter-mode=' + config['netfilter_mode'],
            # VyOS retains ownership of the router resolver configuration.
            '--accept-dns=false']


def main():
    configuration = json.loads(CONFIG.read_text())
    subprocess.run(arguments(configuration), check=True, timeout=20)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'Cannot apply Tailscale preferences: {error}', file=sys.stderr)
        sys.exit(1)
