#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/resolve-kvm-hardware.py"
SPEC = importlib.util.spec_from_file_location("resolve_kvm_hardware", TOOL)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load {TOOL}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
VALIDATOR_PATH = ROOT / "tools/validate-tailscale-ready.py"
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "validate_kvm_ready", VALIDATOR_PATH
)
if VALIDATOR_SPEC is None or VALIDATOR_SPEC.loader is None:
    raise RuntimeError(f"unable to load {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)


class KvmHardwareProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.entries = MODULE.read_registry(ROOT / "profiles/kvm-hardware-providers.conf")

    def test_rock5b_selects_exact_internal_hdmirx_provider(self) -> None:
        result = MODULE.select(self.entries, "rock-5b", True)
        self.assertEqual("rk3588-synopsys-hdmirx", result["provider"])
        self.assertEqual("exact", result["selection"])
        self.assertEqual("yes", result["hid_gadget"])
        MODULE.validate_paths(ROOT, result)

    def test_pi5_uses_generic_capture_without_rockchip_settings(self) -> None:
        result = MODULE.select(self.entries, "raspberry-pi-5", True)
        self.assertEqual("generic-v4l2", result["provider"])
        self.assertEqual("generic", result["selection"])
        self.assertEqual("", result["kernel_config"])

    def test_other_rk3588_board_is_not_inferred_from_soc_name(self) -> None:
        result = MODULE.select(self.entries, "orangepi-5-plus", True)
        self.assertEqual("generic-v4l2", result["provider"])
        self.assertEqual("generic", result["selection"])

    def test_disabled_profile_has_no_hardware_delta(self) -> None:
        result = MODULE.select(self.entries, "rock-5b", False)
        self.assertEqual("disabled", result["provider"])
        self.assertEqual("", result["kernel_config"])

    def test_cli_writes_auditable_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = Path(temp) / "provider.env"
            report = Path(temp) / "provider.json"
            subprocess.run([
                str(TOOL),
                "--board", "rock-5b",
                "--enabled", "yes",
                "--registry", str(ROOT / "profiles/kvm-hardware-providers.conf"),
                "--root", str(ROOT),
                "--output-env", str(env),
                "--output-json", str(report),
            ], check=True)
            self.assertIn("KVM_HARDWARE_PROVIDER=rk3588-synopsys-hdmirx", env.read_text())
            self.assertIn('"selection": "exact"', report.read_text())

    def test_readiness_validator_can_require_host_mode_disabled(self) -> None:
        report = VALIDATOR.validate(
            {"CONFIG_USB_DWC3_HOST": "n"},
            {"CONFIG_USB_DWC3_HOST": "disabled"},
        )
        self.assertEqual("PASS", report[0]["status"])


if __name__ == "__main__":
    unittest.main()
