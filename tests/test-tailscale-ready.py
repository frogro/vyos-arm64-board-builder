#!/usr/bin/env python3

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/validate-tailscale-ready.py"
SPEC = importlib.util.spec_from_file_location("tailscale_ready", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class TailscaleReadyTests(unittest.TestCase):
    def test_builtin_and_module_capabilities(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config"
            path.write_text("CONFIG_NET=y\nCONFIG_TUN=m\n# CONFIG_IPV6 is not set\n")
            config = MODULE.read_kernel_config(path)
            report = MODULE.validate(
                config,
                {
                    "CONFIG_NET": "builtin",
                    "CONFIG_TUN": "available",
                    "CONFIG_IPV6": "available",
                },
            )
        self.assertEqual(
            ["PASS", "FAIL", "PASS"],
            [
            next(item["status"] for item in report if item["symbol"] == symbol)
            for symbol in ["CONFIG_NET", "CONFIG_IPV6", "CONFIG_TUN"]
            ],
        )

    def test_numeric_minimum_rejects_missing_small_and_nonnumeric(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "requirements"
            path.write_text("CONFIG_CMA_SIZE_MBYTES=min:512\n")
            requirements = MODULE.read_requirements(path)
            for value in ['n', 'y', '16', '256', '-1']:
                self.assertEqual('FAIL', MODULE.validate({'CONFIG_CMA_SIZE_MBYTES': value}, requirements)[0]['status'])
            for value in ['512', '768']:
                self.assertEqual('PASS', MODULE.validate({'CONFIG_CMA_SIZE_MBYTES': value}, requirements)[0]['status'])
            self.assertEqual('FAIL', MODULE.validate({}, requirements)[0]['status'])

    def test_profile_has_no_board_or_tailnet_policy(self):
        text = (ROOT / "profiles/tailscale-ready.config").read_text().lower()
        for forbidden in ["rock-5b", "192.168.", "10.3.", "authkey", "tailnet"]:
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
