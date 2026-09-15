#!/usr/bin/env python3
"""Native configuration owner; authentication remains an operational action."""
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import sys

from vyos.config import Config
from vyos import ConfigError, airbag

airbag.enable()
BASE = ['service', 'tailscale']
RUNTIME = Path('/run/vyos-tailscale/config.json')
SERVICE = 'vyos-arm64-tailscaled.service'
HELPER = '/usr/libexec/vyos/vyos-tailscale-apply.py'
BIN = Path('/config/tailscale/bin')


def get_config(config=None):
    conf = config if config else Config()
    if not conf.exists(BASE):
        return None
    return conf.get_config_dict(BASE, key_mangling=('-', '_'), get_first_key=True,
                                no_tag_node_value_mangle=True, with_defaults=True)


def preferences(config):
    routes = config.get('advertise_route', [])
    if isinstance(routes, str):
        routes = [routes]
    normalized = []
    for route in routes:
        try:
            network = ipaddress.ip_network(route, strict=True)
        except ValueError as error:
            raise ConfigError(f'Invalid advertised subnet {route}: {error}') from error
        if network.prefixlen == 0:
            raise ConfigError('Default routes require an exit-node feature; use a specific subnet')
        normalized.append(str(network))
    mode = config.get('netfilter_mode', 'on')
    if mode not in ('on', 'nodivert', 'off'):
        raise ConfigError('Invalid Tailscale netfilter mode')
    return {'advertise_routes': sorted(set(normalized)),
            'accept_routes': 'accept_routes' in config,
            'snat_subnet_routes': 'disable_snat' not in config,
            'netfilter_mode': mode}


def verify(config):
    if config is None:
        return
    preferences(config)
    if 'disable' in config:
        return
    for name in ('tailscale', 'tailscaled'):
        if not os.access(BIN / name, os.X_OK):
            raise ConfigError(f'Install the ARM64 {name} binary at {BIN / name} first')


def generate(config):
    if config is None or 'disable' in config:
        RUNTIME.unlink(missing_ok=True)
        return
    RUNTIME.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = RUNTIME.with_suffix('.tmp')
    temporary.write_text(json.dumps(preferences(config)) + '\n')
    temporary.chmod(0o600)
    temporary.replace(RUNTIME)


def apply(config):
    if config is None or 'disable' in config:
        subprocess.run(['systemctl', 'stop', SERVICE], check=True, timeout=45)
        return
    # ExecStartPost reapplies preferences on daemon recovery as well. An already
    # active daemon needs only a preference update, without disconnecting peers.
    subprocess.run(['systemctl', 'start', SERVICE], check=True, timeout=60)
    subprocess.run([HELPER], check=True, timeout=30)


if __name__ == '__main__':
    try:
        configuration = get_config()
        verify(configuration)
        generate(configuration)
        apply(configuration)
    except (ConfigError, OSError, subprocess.SubprocessError) as error:
        print(f'Tailscale configuration failed: {error}')
        sys.exit(1)
