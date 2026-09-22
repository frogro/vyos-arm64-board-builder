#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from board_catalog import (  # noqa: E402
    audit_catalog,
    kernel_line,
    resolve_requested_reference,
    select_reference,
)


COMMIT = "a" * 40


def profile(target: str, line: str) -> dict:
    return {
        "schema_version": 1,
        "source": {"armbian_commit": COMMIT, "board_file_sha256": "b" * 64},
        "scan": {"status": "resolved"},
        "identity": {
            "board": "rpi4b",
            "target": target,
            "kernel_targets": ["current", "edge"],
            "architecture": "arm64",
            "name": "Raspberry Pi",
            "vendor": "rpi-foundation",
            "board_family": "bcm2711",
            "linux_family": "bcm2711",
        },
        "kernel": {"major_minor": line},
        "device_tree": {"mode": "multi-model", "boot_fdt_file": None},
        "boot": {
            "provider": "raspberrypi-native",
            "armbian_will_build_uboot": False,
            "uboot_metadata_state": "inactive-defaults",
            "handoff": {
                "armbian_mode": "config.txt-direct-kernel",
                "vyos_compatibility": "direct-kernel-sync-required",
            },
        },
    }


class CatalogTests(unittest.TestCase):
    def write_catalog(self, root: Path) -> Path:
        catalog = root / "catalog"
        version = catalog / COMMIT
        (version / "boards" / "rpi4b" / "current").mkdir(parents=True)
        (version / "boards" / "rpi4b" / "edge").mkdir(parents=True)
        (catalog / "LATEST").write_text(COMMIT + "\n", encoding="utf-8")
        inventory = {
            "armbian_commit": COMMIT,
            "boards": [
                {
                    "board": "rpi4b",
                    "targets": ["current", "edge"],
                    "status": "supported",
                }
            ],
        }
        entries = []
        for target, line in (("current", "6.18"), ("edge", "7.1")):
            relative = f"boards/rpi4b/{target}/profile.json"
            data = profile(target, line)
            (version / relative).write_text(json.dumps(data), encoding="utf-8")
            env = "\n".join(
                (
                    f"PROFILE_TARGET={target}",
                    "AVAILABLE_KERNEL_TARGETS=current,edge",
                    f"KERNEL_MAJOR_MINOR={line}",
                    "ARMBIAN_WILL_BUILD_UBOOT=no",
                    "",
                )
            )
            (version / relative).with_name("config.env").write_text(env, encoding="utf-8")
            entries.append(
                {
                    "board": "rpi4b",
                    "target": target,
                    "architecture": "arm64",
                    "provider": "raspberrypi-native",
                    "status": "resolved",
                    "profile": relative,
                }
            )
        index = {
            "armbian_commit": COMMIT,
            "counts": {"resolved": 2},
            "entries": entries,
        }
        (version / "inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
        (version / "index.json").write_text(json.dumps(index), encoding="utf-8")
        return root

    def test_complete_catalog_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            audit = audit_catalog(self.write_catalog(Path(temporary)))
        self.assertEqual([], [item for item in audit.findings if item.level == "FAIL"])
        self.assertEqual(2, len(audit.profiles))

    def test_auto_reference_matches_kernel_and_priority(self) -> None:
        candidates = [profile("edge", "6.18"), profile("current", "6.18")]
        selected = select_reference(candidates, "6.18.44-vyos")
        self.assertIsNotNone(selected)
        self.assertEqual("current", selected["identity"]["target"])

    def test_override_is_developer_escape_hatch(self) -> None:
        candidates = [profile("edge", "7.1"), profile("current", "6.18")]
        selected = select_reference(candidates, "6.18.44-vyos", override="edge")
        self.assertIsNotNone(selected)
        self.assertEqual("edge", selected["identity"]["target"])

    def test_kernel_line_parser(self) -> None:
        self.assertEqual("6.18", kernel_line("6.18.44-vyos"))

    def test_model_resolves_to_armbian_board(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            audit = audit_catalog(self.write_catalog(Path(temporary)))
        model = {
            "model": "raspberry-pi-5",
            "name": "Raspberry Pi 5",
            "armbian_board": "rpi4b",
            "soc": "bcm2712",
            "device_tree": {"boot_fdt_file": "broadcom/bcm2712-rpi-5-b.dtb"},
            "boot": {"provider": "raspberrypi-native"},
        }
        selected = resolve_requested_reference(
            audit, [model], "raspberry-pi-5", "6.18.44-vyos"
        )
        self.assertEqual("rpi4b", selected["armbian_board"])
        self.assertEqual("current", selected["target"])
        self.assertEqual("broadcom/bcm2712-rpi-5-b.dtb", selected["boot_fdt_file"])


if __name__ == "__main__":
    unittest.main()
