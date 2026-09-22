#!/usr/bin/env python3

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/patch-vyos-grub-board-dtb.py"


def load_patcher():
    spec = importlib.util.spec_from_file_location(
        "grub_board_dtb_patcher",
        SCRIPT,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


UPSTREAM_TEMPLATE = """\
menuentry "{{ version_name }}" --id {{ version_uuid }} {
    set boot_opts="{{ boot_opts_rendered }}"
    linux "/boot/{{ version_name }}/vmlinuz" ${boot_opts}
    initrd "/boot/{{ version_name }}/initrd.img"
}
"""


def make_template(rootfs: Path, content: str = UPSTREAM_TEMPLATE) -> Path:
    target = (
        rootfs
        / "usr/share/vyos/templates/grub/grub_vyos_version.j2"
    )
    target.parent.mkdir(parents=True)
    target.write_text(content)
    return target


class GrubBoardDtbPersistenceTest(unittest.TestCase):
    def test_adds_board_dtb_before_linux_and_is_idempotent(self):
        patcher = load_patcher()

        with tempfile.TemporaryDirectory() as temp:
            rootfs = Path(temp)
            target = make_template(rootfs)

            changed = patcher.patch_grub_version_template(
                rootfs,
                "vendor/example-board.dtb",
            )
            self.assertTrue(changed)

            expected = (
                '    devicetree '
                '"/boot/{{ version_name }}/dtb/vendor/example-board.dtb"'
            )

            updated = target.read_text()

            self.assertEqual(updated.count(expected), 1)
            self.assertIn(
                expected + "\n" + patcher.LINUX_LINE,
                updated,
            )

            changed = patcher.patch_grub_version_template(
                rootfs,
                "vendor/example-board.dtb",
            )
            self.assertFalse(changed)

            self.assertEqual(
                target.read_text().count(expected),
                1,
            )

    def test_invalid_dtb_paths_fail_closed(self):
        patcher = load_patcher()

        invalid_paths = (
            "",
            "/absolute/board.dtb",
            "../board.dtb",
            "vendor/../board.dtb",
            "vendor//board.dtb",
            'vendor/"board.dtb',
        )

        with tempfile.TemporaryDirectory() as temp:
            rootfs = Path(temp)
            make_template(rootfs)

            for value in invalid_paths:
                with self.subTest(value=value):
                    with self.assertRaises(SystemExit):
                        patcher.patch_grub_version_template(
                            rootfs,
                            value,
                        )

    def test_unknown_upstream_template_fails_closed(self):
        patcher = load_patcher()

        with tempfile.TemporaryDirectory() as temp:
            rootfs = Path(temp)

            make_template(
                rootfs,
                """\
menuentry "{{ version_name }}" {
    linuxefi "/boot/{{ version_name }}/vmlinuz"
}
""",
            )

            with self.assertRaises(SystemExit):
                patcher.patch_grub_version_template(
                    rootfs,
                    "vendor/example-board.dtb",
                )

    def test_conflicting_existing_dtb_fails_closed(self):
        patcher = load_patcher()

        with tempfile.TemporaryDirectory() as temp:
            rootfs = Path(temp)

            make_template(
                rootfs,
                UPSTREAM_TEMPLATE.replace(
                    patcher.LINUX_LINE,
                    '    devicetree '
                    '"/boot/{{ version_name }}/dtb/vendor/other-board.dtb"\n'
                    + patcher.LINUX_LINE,
                ),
            )

            with self.assertRaises(SystemExit):
                patcher.patch_grub_version_template(
                    rootfs,
                    "vendor/example-board.dtb",
                )

    def test_patcher_contains_no_rock5b_policy(self):
        source = SCRIPT.read_text().lower()

        self.assertNotIn("rock-5b", source)
        self.assertNotIn("rk3588", source)
        self.assertNotIn("fc400000", source)


if __name__ == "__main__":
    unittest.main()
