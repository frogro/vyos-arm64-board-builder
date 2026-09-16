#!/usr/bin/env python3
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HELPER = ROOT / "tools/common-firstboot/setup-transaction.sh"

class Helpers(unittest.TestCase):
    def transaction(self, changed=True, bad_set=False, bad_commit=False, bad_save=False):
        with tempfile.TemporaryDirectory() as tmp:
            log = pathlib.Path(tmp) / "calls"
            script = f"""shopt -s expand_aliases
alias set='mock_set'
mock_set() {{ echo set >> '{log}'; return {int(bad_set)}; }}
discard() {{ echo discard >> '{log}'; }}
commit() {{ echo commit >> '{log}'; return {int(bad_commit)}; }}
save() {{ echo save >> '{log}'; return {int(bad_save)}; }}
api() {{ return {0 if changed else 1}; }}
API=api
source '{HELPER}'
setup_set interfaces ethernet eth0 address dhcp
setup_commit_save
"""
            result = subprocess.run(["bash", "-c", script], capture_output=True)
            return result.returncode, log.read_text().splitlines()

    def test_unchanged_is_success(self):
        self.assertEqual(self.transaction(changed=False), (0, ["set", "save"]))

    def test_failed_set_never_commits(self):
        rc, calls = self.transaction(bad_set=True)
        self.assertNotEqual(rc, 0)
        self.assertEqual(calls, ["set", "discard"])

    def test_failed_commit_never_saves(self):
        rc, calls = self.transaction(bad_commit=True)
        self.assertNotEqual(rc, 0)
        self.assertEqual(calls, ["set", "commit", "discard"])

    def test_save_failure_propagates(self):
        self.assertNotEqual(self.transaction(bad_save=True)[0], 0)

    def test_locale_preserves_other_values_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "etc").mkdir()
            env = root / "etc/environment"
            env.write_text('HTTP_PROXY="http://example.invalid"\nLANG=de_DE\nLC_ALL=old\n')
            command = ["python3", str(ROOT / "tools/common-firstboot/set-utf8-locale.py"), tmp]
            subprocess.run(command, check=True)
            first = env.read_text()
            subprocess.run(command, check=True)
            self.assertEqual(first, env.read_text())
            self.assertIn('HTTP_PROXY="http://example.invalid"', first)
            self.assertEqual(first.count("LANG="), 1)
            self.assertIn("LANG=C.UTF-8", first)

if __name__ == "__main__":
    unittest.main()
