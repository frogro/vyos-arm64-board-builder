#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "tools" / "generate-board-config.py"
SPEC = importlib.util.spec_from_file_location(
    "generate_board_config",
    MODULE_PATH,
)

if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load {MODULE_PATH}")

GENERATE_BOARD_CONFIG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATE_BOARD_CONFIG)


class ConfigValidationTests(unittest.TestCase):
    def test_boot_only_closure_tracks_transitive_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kernel = root / "kernel"
            output = root / "output"
            kernel.mkdir()
            output.mkdir()

            (kernel / "Kconfig").write_text(
                """mainmenu \"validation test\"

config BOOT_DEP
    bool \"Boot dependency\"

config BOOT_ROOT
    tristate \"Boot root\"
    depends on BOOT_DEP

config RUNTIME_DRIVER
    tristate \"Runtime driver\"
""",
                encoding="utf-8",
            )

            base = root / "base.config"
            base.write_text(
                "# CONFIG_BOOT_DEP is not set\n"
                "# CONFIG_BOOT_ROOT is not set\n"
                "# CONFIG_RUNTIME_DRIVER is not set\n",
                encoding="utf-8",
            )

            requested = root / "strict.config"
            requested.write_text(
                "CONFIG_BOOT_ROOT=y\n",
                encoding="utf-8",
            )

            resolved = GENERATE_BOARD_CONFIG.run_kconfig_closure(
                kernel=kernel,
                vyos_config=base,
                raw_fragment=requested,
                out=output,
                directory="strict-kconfig-closure",
            )

            self.assertEqual(
                GENERATE_BOARD_CONFIG.read_config(resolved),
                {
                    "CONFIG_BOOT_DEP": "y",
                    "CONFIG_BOOT_ROOT": "y",
                },
            )
            self.assertTrue(
                (
                    output
                    / "strict-kconfig-closure"
                    / "dependency-trace.txt"
                ).is_file()
            )

    def test_exact_value_is_accepted(self) -> None:
        self.assertEqual(
            GENERATE_BOARD_CONFIG.validation_state(
                "CONFIG_EXAMPLE",
                "y",
                "y",
                {"CONFIG_EXAMPLE"},
            ),
            "OK",
        )

    def test_runtime_driver_may_be_normalized_to_module(self) -> None:
        self.assertEqual(
            GENERATE_BOARD_CONFIG.validation_state(
                "CONFIG_BT",
                "y",
                "m",
                set(),
            ),
            "OK-MODULE",
        )

    def test_runtime_driver_may_remain_builtin(self) -> None:
        self.assertEqual(
            GENERATE_BOARD_CONFIG.validation_state(
                "CONFIG_EXAMPLE",
                "m",
                "y",
                set(),
            ),
            "OK-BUILTIN",
        )

    def test_boot_dependency_must_not_become_module(self) -> None:
        self.assertEqual(
            GENERATE_BOARD_CONFIG.validation_state(
                "CONFIG_MMC",
                "y",
                "m",
                {"CONFIG_MMC"},
            ),
            "FAIL",
        )

    def test_runtime_driver_must_not_disappear(self) -> None:
        for requested in ("y", "m"):
            with self.subTest(requested=requested):
                self.assertEqual(
                    GENERATE_BOARD_CONFIG.validation_state(
                        "CONFIG_EXAMPLE",
                        requested,
                        "n",
                        set(),
                    ),
                    "FAIL",
                )


if __name__ == "__main__":
    unittest.main()
