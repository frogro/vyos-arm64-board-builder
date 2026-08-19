#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from select_hardware_reference import choose, discover_targets  # noqa: E402


class HardwareReferenceTests(unittest.TestCase):
    def test_discovers_all_literal_targets_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "board.conf"
            path.write_text(
                'BOARD_NAME="Example"\nKERNEL_TARGET="vendor,current,edge,vendor-rt"\n',
                encoding="utf-8",
            )
            self.assertEqual(
                ["vendor", "current", "edge", "vendor-rt"], discover_targets(path)
            )

    def test_auto_uses_exact_current_before_edge(self) -> None:
        selected = choose(
            [
                {"target": "edge", "kernel_major_minor": "6.18"},
                {"target": "current", "kernel_major_minor": "6.18"},
            ],
            "6.18.44-vyos",
            "auto",
        )
        self.assertEqual("current", selected["target"])

    def test_auto_fails_closed_without_exact_line(self) -> None:
        with self.assertRaisesRegex(ValueError, "no exact Armbian reference"):
            choose(
                [{"target": "current", "kernel_major_minor": "6.12"}],
                "6.18.44-vyos",
                "auto",
            )

    def test_developer_override_can_select_nonmatching_edge(self) -> None:
        selected = choose(
            [
                {"target": "current", "kernel_major_minor": "6.18"},
                {"target": "edge", "kernel_major_minor": "7.1"},
            ],
            "6.18.44-vyos",
            "edge",
        )
        self.assertEqual("edge", selected["target"])


if __name__ == "__main__":
    unittest.main()
