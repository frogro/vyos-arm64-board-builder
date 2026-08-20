#!/usr/bin/env python3

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "release-identity.py"
SPEC = importlib.util.spec_from_file_location("release_identity", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ReleaseIdentityTests(unittest.TestCase):
    def test_nightly_style_names(self):
        self.assertEqual(
            MODULE.derive("1.5-rolling-202608200300", "raspberry-pi-5"),
            {
                "VYOS_VERSION": "1.5-rolling-202608200300",
                "RELEASE_BASENAME": (
                    "vyos-1.5-rolling-202608200300-raspberry-pi-5"
                ),
                "RELEASE_TAG": (
                    "2026.08.20-0300-rolling-raspberry-pi-5"
                ),
            },
        )

    def test_invalid_version_is_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.derive("rolling-latest", "rock-5b")

    def test_invalid_board_is_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.derive("1.5-rolling-202608200300", "Rock 5B")


if __name__ == "__main__":
    unittest.main()
