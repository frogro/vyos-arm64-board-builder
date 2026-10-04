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
        self.assertEqual(
            "",
            result["dt_overlay"],
        )
        self.assertEqual(
            "profiles/base-hardware/kernel-patches/rk3588-synopsys-hdmirx",
            result["kernel_patch_dir"],
        )
        MODULE.validate_paths(ROOT, result)

    def test_rock5b_preserves_usb_a_host_routing(self) -> None:
        result = MODULE.select(self.entries, "rock-5b", True)
        self.assertEqual("", result["dt_overlay"])
        for path in (
            "profiles/kvm-hardware/dt-overlays/rock5b-fc400000-peripheral.dts",
            "patches/kernel/0001-rockchip-usb2phy-vbus-always-on.patch",
            "patches/kernel/0002-rockchip-usbdp-fixed-peripheral-bvalid.patch",
        ):
            self.assertFalse((ROOT / path).exists())
        provider = (ROOT / "profiles/kvm-hardware/runtime/rk3588-synopsys-hdmirx.env").read_text()
        self.assertIn("KVM_GADGET_UDC_USBC=fc000000.usb", provider)
        self.assertNotIn("fc400000", provider)

    def test_kvm_profile_adds_gadget_diagnostics_and_virtual_media_only_when_enabled(self) -> None:
        required = (ROOT / "profiles/kvm-over-ip.config").read_text(encoding="utf-8")
        ready = (ROOT / "profiles/kvm-over-ip-ready.config").read_text(encoding="utf-8")
        build = (ROOT / "build.sh").read_text(encoding="utf-8")

        for expected in (
            "CONFIG_USB_GADGET_DEBUG_FS=y",
            "CONFIG_USB_CONFIGFS_F_LB_SS=y",
            "CONFIG_USB_CONFIGFS_F_HID=y",
            "CONFIG_USB_CONFIGFS_MASS_STORAGE=y",
        ):
            self.assertIn(expected, required)

        for expected in (
            "CONFIG_USB_GADGET_DEBUG_FS=builtin",
            "CONFIG_USB_CONFIGFS_F_LB_SS=builtin",
            "CONFIG_USB_CONFIGFS_F_HID=builtin",
            "CONFIG_USB_CONFIGFS_MASS_STORAGE=builtin",
        ):
            self.assertIn(expected, ready)

        self.assertIn('if [[ "${kvm_over_ip}" == "yes" ]]; then', build)
        self.assertIn('profiles/kvm-over-ip.config', build)

    def test_rock5b_profile_d_enables_encoder_only_mpp(self) -> None:
        config = (ROOT / "profiles/base-hardware/rock-5b.config").read_text(encoding="utf-8")
        ready = (ROOT / "profiles/base-hardware/rock-5b-ready.config").read_text(encoding="utf-8")
        for expected in (
            "CONFIG_ROCKCHIP_MPP_SERVICE=y",
            "CONFIG_ROCKCHIP_MPP_PROC_FS=y",
            "CONFIG_ROCKCHIP_MPP_RKVENC2=y",
            "# CONFIG_ROCKCHIP_MPP_RKVENC2_DEVFREQ is not set",
            "# CONFIG_ROCKCHIP_MPP_RKVDEC2 is not set",
        ):
            self.assertIn(expected, config)
        for expected in (
            "CONFIG_ROCKCHIP_MPP_SERVICE=builtin",
            "CONFIG_ROCKCHIP_MPP_PROC_FS=builtin",
            "CONFIG_ROCKCHIP_MPP_RKVENC2=builtin",
            "CONFIG_ROCKCHIP_MPP_RKVENC2_DEVFREQ=disabled",
            "CONFIG_ROCKCHIP_MPP_RKVDEC2=disabled",
        ):
            self.assertIn(expected, ready)

    def test_pi5_uses_generic_capture_with_exact_usb_c_routing(self) -> None:
        result = MODULE.select(self.entries, "raspberry-pi-5", True)
        self.assertEqual("pi5-usbc", result["provider"])
        self.assertEqual("generic-v4l2", result["capture_backend"])
        self.assertEqual("exact", result["selection"])
        self.assertTrue(result["dt_overlay"].endswith("pi5-usbc-peripheral.dts"))
        self.assertEqual("runtime", result["hid_gadget"])

    def test_e52c_rejects_d_but_allows_disabled_provider(self):
        with self.assertRaises(ValueError):
            MODULE.select(self.entries, "radxa-e52c", True)
        self.assertEqual("disabled", MODULE.select(self.entries, "radxa-e52c", False)["provider"])

    def test_other_rk3588_board_is_not_inferred_from_soc_name(self) -> None:
        result = MODULE.select(self.entries, "orangepi-5-plus", True)
        self.assertEqual("generic-v4l2", result["provider"])
        self.assertEqual("generic", result["selection"])
        self.assertEqual("", result["dt_overlay"])
        self.assertEqual("", result["kernel_patch_dir"])

    def test_disabled_profile_has_no_hardware_delta(self) -> None:
        result = MODULE.select(self.entries, "rock-5b", False)
        self.assertEqual("disabled", result["provider"])
        self.assertEqual("", result["kernel_config"])
        self.assertEqual("", result["kernel_patch_dir"])

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
            env_text = env.read_text()
            self.assertIn("KVM_HARDWARE_PROVIDER=rk3588-synopsys-hdmirx", env_text)
            self.assertIn(
                "KVM_HARDWARE_KERNEL_PATCH_DIR=profiles/base-hardware/kernel-patches/"
                "rk3588-synopsys-hdmirx",
                env_text,
            )
            self.assertIn(
                "KVM_HARDWARE_DT_OVERLAY=''",
                env_text,
            )
            self.assertIn('"selection": "exact"', report.read_text())

    def test_readiness_validator_can_require_host_mode_disabled(self) -> None:
        report = VALIDATOR.validate(
            {"CONFIG_USB_DWC3_HOST": "n"},
            {"CONFIG_USB_DWC3_HOST": "disabled"},
        )
        self.assertEqual("PASS", report[0]["status"])


if __name__ == "__main__":
    unittest.main()
