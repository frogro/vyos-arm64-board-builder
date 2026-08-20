#!/usr/bin/env python3
import importlib.util
import pathlib
import json
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("feature_profile", ROOT / "tools/feature-profile.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FeatureProfileTests(unittest.TestCase):
    def test_profile_matrix(self):
        cases = {
            (False, False): "base",
            (True, False): "network",
            (False, True): "tailscale",
            (True, True): "network-tailscale",
        }
        for flags, expected in cases.items():
            with self.subTest(flags=flags):
                self.assertEqual(MODULE.derive(*flags)["profile"], expected)

    def test_boolean_parser(self):
        for value in ("yes", "true", "1", "on", "Y"):
            self.assertTrue(MODULE.parse_bool(value))
        for value in ("no", "false", "0", "off", "N"):
            self.assertFalse(MODULE.parse_bool(value))
        with self.assertRaises(ValueError):
            MODULE.parse_bool("maybe")

    def test_cli_writes_matching_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            env_path = pathlib.Path(directory) / "profile.env"
            json_path = pathlib.Path(directory) / "profile.json"
            subprocess.run(
                [
                    str(ROOT / "tools/feature-profile.py"),
                    "--extended-network", "yes",
                    "--tailscale-subnet-router", "no",
                    "--output-env", str(env_path),
                    "--output-json", str(json_path),
                ],
                check=True,
            )
            self.assertIn("BUILD_PROFILE=network\n", env_path.read_text())
            self.assertEqual(
                json.loads(json_path.read_text())["profile"],
                "network",
            )


if __name__ == "__main__":
    unittest.main()
