#!/usr/bin/env python3

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/patch-vyos-arm-cpu-opmode.py"
UPSTREAM = Path("/tmp/vyos-1x/src/op_mode/cpu.py")


def load_patcher():
    spec = importlib.util.spec_from_file_location("arm_cpu_patcher", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class ArmCpuOpmodeTest(unittest.TestCase):
    def test_patch_preserves_x86_and_adds_arm_fallbacks(self):
        patcher = load_patcher()
        if UPSTREAM.is_file():
            original = UPSTREAM.read_text()
        else:
            original = """import sys
import vyos.opmode
from vyos.utils.cpu import get_cpus
from vyos.utils.cpu import get_core_count
from jinja2 import Template

%s

def _get_summary_data():
    cpu_data = get_cpus()
    %s
""" % (patcher.OLD_TEMPLATE, patcher.OLD_SUMMARY)

        with tempfile.TemporaryDirectory() as temp:
            rootfs = Path(temp)
            target = rootfs / "usr/libexec/vyos/op_mode/cpu.py"
            target.parent.mkdir(parents=True)
            target.write_text(original)

            self.assertTrue(patcher.patch_cpu_opmode(rootfs))
            updated = target.read_text()
            self.assertIn("from jinja2 import Template", updated)
            self.assertIn("'vendor_id' in cpu", updated)
            self.assertIn("'CPU implementer' in cpu", updated)
            self.assertIn("'CPU architecture' in cpu", updated)
            self.assertIn("'CPU part', 'unknown'", updated)
            self.assertFalse(patcher.patch_cpu_opmode(rootfs))

    def test_unknown_upstream_revision_fails_closed(self):
        patcher = load_patcher()
        with tempfile.TemporaryDirectory() as temp:
            rootfs = Path(temp)
            target = rootfs / "usr/libexec/vyos/op_mode/cpu.py"
            target.parent.mkdir(parents=True)
            target.write_text("from jinja2 import Template\n")
            with self.assertRaises(SystemExit):
                patcher.patch_cpu_opmode(rootfs)


if __name__ == "__main__":
    unittest.main()
