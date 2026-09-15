#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
vyos = types.ModuleType('vyos')
vyos.ConfigError = type('ConfigError', (Exception,), {})
vyos.airbag = types.SimpleNamespace(enable=lambda: None)
config_module = types.ModuleType('vyos.config')
config_module.Config = object
sys.modules['vyos'] = vyos
sys.modules['vyos.config'] = config_module


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


owner = load('owner', 'tools/tailscale-cli/service_tailscale.py')
helper = load('helper', 'tools/tailscale-cli/vyos-tailscale-apply.py')


class Tests(unittest.TestCase):
    def test_route_removal_explicitly_clears_old_preference(self):
        before = helper.arguments(owner.preferences({'advertise_route': ['192.0.2.0/24', '2001:db8::/64']}))
        after = helper.arguments(owner.preferences({}))
        self.assertIn('--advertise-routes=192.0.2.0/24,2001:db8::/64', before)
        self.assertIn('--advertise-routes=', after)
        self.assertIn('--accept-routes=false', after)
        self.assertIn('--snat-subnet-routes=true', after)
        self.assertIn('--accept-dns=false', after)
        self.assertNotIn('up', after)
        self.assertNotIn('logout', after)

    def test_reject_host_bits_default_routes_and_command_injection(self):
        for route in ['192.0.2.1/24', '0.0.0.0/0', '::/0', '192.0.2.0/24;reboot']:
            with self.subTest(route=route), self.assertRaises(vyos.ConfigError):
                owner.preferences({'advertise_route': [route]})

    def test_ipv6_canonicalization_and_single_route(self):
        self.assertEqual(owner.preferences({'advertise_route': '2001:db8:0::/64'})['advertise_routes'], ['2001:db8::/64'])

    def test_missing_binaries_fail_before_generation(self):
        with patch.object(owner.os, 'access', return_value=False):
            with self.assertRaises(vyos.ConfigError):
                owner.verify({})
            owner.verify({'disable': ''})
            owner.verify(None)

    def test_runtime_disable_removes_only_generated_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / 'run/config.json'
            state = Path(directory) / 'tailscaled.state'
            state.write_text('retained identity')
            with patch.object(owner, 'RUNTIME', runtime):
                owner.generate({'accept_routes': '', 'disable_snat': ''})
                self.assertTrue(json.loads(runtime.read_text())['accept_routes'])
                self.assertEqual(runtime.stat().st_mode & 0o777, 0o600)
                owner.generate({'disable': ''})
                self.assertFalse(runtime.exists())
                owner.generate(None)
            self.assertEqual(state.read_text(), 'retained identity')

    def test_disable_stops_without_logout_and_update_does_not_restart(self):
        with patch.object(owner.subprocess, 'run') as run:
            owner.apply(None)
            self.assertEqual(run.call_args.args[0], ['systemctl', 'stop', owner.SERVICE])
            run.reset_mock()
            owner.apply({})
            self.assertEqual(run.call_args_list[0].args[0], ['systemctl', 'start', owner.SERVICE])
            self.assertEqual(run.call_args_list[1].args[0], [owner.HELPER])

    def test_daemon_recovery_requires_native_configuration(self):
        unit = (ROOT / 'tools/common-firstboot/vyos-arm64-tailscaled.service').read_text()
        self.assertIn('ConditionPathExists=/run/vyos-tailscale/config.json', unit)
        self.assertIn('ExecStartPost=/usr/libexec/vyos/vyos-tailscale-apply.py', unit)
        self.assertIn('--state=/config/tailscale/state/tailscaled.state', unit)


if __name__ == '__main__':
    unittest.main()
