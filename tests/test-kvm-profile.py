#!/usr/bin/env python3
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class KvmProfileTests(unittest.TestCase):
    def test_kernel_profile_is_opt_in_and_policy_free(self):
        text = (ROOT / "profiles/kvm-over-ip.config").read_text()
        self.assertIn("CONFIG_USB_VIDEO_CLASS=m", text)
        self.assertIn("CONFIG_USB_CONFIGFS_F_HID=y", text)
        lowered = text.lower()
        for forbidden in (
            "password",
            "token",
            "192.168.",
            "listen_address",
            "tcp_port",
        ):
            self.assertNotIn(forbidden, lowered)

    def test_readiness_profile_matches_kernel_profile(self):
        requested = (ROOT / "profiles/kvm-over-ip.config").read_text()
        requirements = (ROOT / "profiles/kvm-over-ip-ready.config").read_text()
        for line in requirements.splitlines():
            if line.startswith("CONFIG_"):
                symbol = line.split("=", 1)[0]
                self.assertIn(symbol + "=", requested)


if __name__ == "__main__":
    unittest.main()
