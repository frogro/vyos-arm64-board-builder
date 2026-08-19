#!/usr/bin/env python3

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "tools" / "validate_model_requirements.py"
SPEC = importlib.util.spec_from_file_location(
    "validate_model_requirements",
    MODULE_PATH,
)

if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load {MODULE_PATH}")

VALIDATE_MODEL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATE_MODEL)


class ModelRequirementTests(unittest.TestCase):
    def run_validator(self, kernel_value: str) -> int:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = root / "fixtures" / "expected.config"
            fixture.parent.mkdir()
            fixture.write_text(
                "CONFIG_RUNTIME_DRIVER=y\n",
                encoding="utf-8",
            )

            model = root / "model.json"
            model.write_text(
                json.dumps(
                    {
                        "model": "test-board",
                        "device_tree": {
                            "boot_fdt_file": "vendor/test-board.dtb"
                        },
                        "requirements": {
                            "hardware_config": "fixtures/expected.config"
                        },
                    }
                ),
                encoding="utf-8",
            )

            kernel_config = root / "kernel.config"
            kernel_config.write_text(
                f"CONFIG_RUNTIME_DRIVER={kernel_value}\n",
                encoding="utf-8",
            )

            dtb_root = root / "dtbs"
            dtb = dtb_root / "vendor" / "test-board.dtb"
            dtb.parent.mkdir(parents=True)
            dtb.write_bytes(b"dtb")

            argv = [
                str(MODULE_PATH),
                "--root",
                str(root),
                "--model",
                str(model),
                "--kernel-config",
                str(kernel_config),
                "--dtb-root",
                str(dtb_root),
            ]

            with (
                patch.object(sys, "argv", argv),
                redirect_stdout(StringIO()),
                redirect_stderr(StringIO()),
            ):
                return VALIDATE_MODEL.main()

    def test_main_accepts_runtime_module(self) -> None:
        self.assertEqual(0, self.run_validator("m"))

    def test_main_rejects_disabled_runtime_driver(self) -> None:
        self.assertEqual(1, self.run_validator("n"))

    def test_builtin_requirement_accepts_module(self) -> None:
        self.assertTrue(
            VALIDATE_MODEL.requirement_satisfied("y", "m")
        )

    def test_module_requirement_accepts_builtin(self) -> None:
        self.assertTrue(
            VALIDATE_MODEL.requirement_satisfied("m", "y")
        )

    def test_enabled_requirement_rejects_disabled(self) -> None:
        for expected in ("y", "m"):
            with self.subTest(expected=expected):
                self.assertFalse(
                    VALIDATE_MODEL.requirement_satisfied(expected, "n")
                )

    def test_non_tristate_requirement_remains_exact(self) -> None:
        self.assertTrue(
            VALIDATE_MODEL.requirement_satisfied('"value"', '"value"')
        )
        self.assertFalse(
            VALIDATE_MODEL.requirement_satisfied('"value"', '"other"')
        )

    def test_read_config_records_disabled_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "config"
            config.write_text(
                "CONFIG_BUILTIN=y\n"
                "CONFIG_MODULE=m\n"
                "# CONFIG_DISABLED is not set\n",
                encoding="utf-8",
            )
            self.assertEqual(
                {
                    "CONFIG_BUILTIN": "y",
                    "CONFIG_MODULE": "m",
                    "CONFIG_DISABLED": "n",
                },
                VALIDATE_MODEL.read_config(config),
            )


if __name__ == "__main__":
    unittest.main()
