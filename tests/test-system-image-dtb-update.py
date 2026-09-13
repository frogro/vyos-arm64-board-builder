#!/usr/bin/env python3

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/patch-vyos-system-image-dtb.py"


def load_patcher():
    spec = importlib.util.spec_from_file_location(
        "system_image_dtb_patcher",
        SCRIPT,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def load_generated_helpers(patcher):
    namespace = {
        "Path": Path,
        "loads": json.loads,
        "copy": shutil.copy,
    }
    exec(patcher.HELPER_BLOCK, namespace)
    return namespace


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


class SystemImageDtbUpdateTest(unittest.TestCase):
    def test_matching_board_copies_dtb(self):
        patcher = load_patcher()
        helpers = load_generated_helpers(patcher)
        copy_dtb = helpers["_copy_board_dtb_from_update_iso"]

        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            iso = base / "iso"
            root = base / "root"
            profile = base / "profile.json"

            write_json(
                profile,
                {
                    "schema": 2,
                    "architecture": "arm64",
                    "board": "vendor-example",
                },
            )

            write_json(
                iso / "board-manifest.json",
                {
                    "schema": 3,
                    "architecture": "arm64",
                    "board": "vendor-example",
                    "device_tree": "vendor/example-board.dtb",
                },
            )

            source = (
                iso
                / "live"
                / "dtb"
                / "vendor"
                / "example-board.dtb"
            )
            source.parent.mkdir(parents=True)
            source.write_bytes(b"example-dtb")

            changed = copy_dtb(
                iso,
                root,
                "1.5-test",
                profile_path=profile,
            )

            self.assertTrue(changed)

            destination = (
                root
                / "boot"
                / "1.5-test"
                / "dtb"
                / "vendor"
                / "example-board.dtb"
            )

            self.assertEqual(
                destination.read_bytes(),
                b"example-dtb",
            )

    def test_board_or_architecture_mismatch_fails(self):
        patcher = load_patcher()
        helpers = load_generated_helpers(patcher)
        copy_dtb = helpers["_copy_board_dtb_from_update_iso"]

        for field, update_value in (
            ("board", "other-board"),
            ("architecture", "amd64"),
        ):
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory() as temp:
                    base = Path(temp)
                    iso = base / "iso"
                    root = base / "root"
                    profile = base / "profile.json"

                    write_json(
                        profile,
                        {
                            "schema": 2,
                            "architecture": "arm64",
                            "board": "vendor-example",
                        },
                    )

                    manifest = {
                        "schema": 3,
                        "architecture": "arm64",
                        "board": "vendor-example",
                        "device_tree": "vendor/example-board.dtb",
                    }
                    manifest[field] = update_value

                    write_json(
                        iso / "board-manifest.json",
                        manifest,
                    )

                    with self.assertRaises(RuntimeError):
                        copy_dtb(
                            iso,
                            root,
                            "1.5-test",
                            profile_path=profile,
                        )

    def test_missing_manifest_fails_for_builder_system(self):
        patcher = load_patcher()
        helpers = load_generated_helpers(patcher)
        copy_dtb = helpers["_copy_board_dtb_from_update_iso"]

        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            profile = base / "profile.json"

            write_json(
                profile,
                {
                    "schema": 2,
                    "architecture": "arm64",
                    "board": "vendor-example",
                },
            )

            with self.assertRaises(RuntimeError):
                copy_dtb(
                    base / "iso",
                    base / "root",
                    "1.5-test",
                    profile_path=profile,
                )

    def test_invalid_dtb_paths_fail(self):
        patcher = load_patcher()
        helpers = load_generated_helpers(patcher)
        validate = helpers["_validate_board_update_dtb_path"]

        for value in (
            "",
            "/vendor/example.dtb",
            "../example.dtb",
            "vendor/../example.dtb",
            "vendor//example.dtb",
            r"vendor\example.dtb",
            'vendor/"example.dtb',
            "vendor/example.img",
        ):
            with self.subTest(value=value):
                with self.assertRaises(RuntimeError):
                    validate(value)

    def test_missing_dtb_file_fails(self):
        patcher = load_patcher()
        helpers = load_generated_helpers(patcher)
        copy_dtb = helpers["_copy_board_dtb_from_update_iso"]

        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            iso = base / "iso"
            profile = base / "profile.json"

            write_json(
                profile,
                {
                    "schema": 2,
                    "architecture": "arm64",
                    "board": "vendor-example",
                },
            )

            write_json(
                iso / "board-manifest.json",
                {
                    "schema": 3,
                    "architecture": "arm64",
                    "board": "vendor-example",
                    "device_tree": "vendor/example-board.dtb",
                },
            )

            with self.assertRaises(RuntimeError):
                copy_dtb(
                    iso,
                    base / "root",
                    "1.5-test",
                    profile_path=profile,
                )

    def test_non_builder_vyos_keeps_upstream_behavior(self):
        patcher = load_patcher()
        helpers = load_generated_helpers(patcher)
        copy_dtb = helpers["_copy_board_dtb_from_update_iso"]

        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)

            changed = copy_dtb(
                base / "iso",
                base / "root",
                "1.5-test",
                profile_path=base / "does-not-exist.json",
            )

            self.assertFalse(changed)
            self.assertFalse((base / "root" / "boot").exists())

    def test_patcher_is_idempotent_and_fails_closed(self):
        patcher = load_patcher()

        with tempfile.TemporaryDirectory() as temp:
            rootfs = Path(temp)
            target = rootfs / patcher.TARGET_REL
            target.parent.mkdir(parents=True)

            target.write_text(
                "from pathlib import Path\n"
                "from shutil import copy\n"
                "from json import loads\n\n"
                "@compat.grub_cfg_update\n"
                "def add_image(image_path):\n"
                + patcher.ROOT_DIR_ANCHOR
                + "\n"
            )

            self.assertTrue(
                patcher.patch_image_installer(rootfs)
            )

            updated = target.read_text()

            self.assertEqual(
                updated.count(
                    "def _copy_board_dtb_from_update_iso("
                ),
                1,
            )

            self.assertEqual(
                updated.count(
                    "_copy_board_dtb_from_update_iso(\n"
                    "            Path(DIR_ISO_MOUNT),"
                ),
                1,
            )

            self.assertFalse(
                patcher.patch_image_installer(rootfs)
            )

    def test_patcher_contains_no_board_specific_policy(self):
        source = SCRIPT.read_text().lower()

        self.assertNotIn("rock-5b", source)
        self.assertNotIn("rk3588", source)
        self.assertNotIn("fc400000", source)


if __name__ == "__main__":
    unittest.main()
