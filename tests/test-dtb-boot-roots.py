#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "tools" / "dtb-boot-roots.py"
SPEC = importlib.util.spec_from_file_location("dtb_boot_roots", MODULE_PATH)

if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load {MODULE_PATH}")

DTB_BOOT_ROOTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DTB_BOOT_ROOTS)


class MmcNodeRecognitionTests(unittest.TestCase):
    def test_controller_unit_name_is_mmc(self) -> None:
        self.assertTrue(
            DTB_BOOT_ROOTS.looks_like_mmc(
                "/soc@107c000000/mmc@1100000",
                {"compatible": ["brcm,bcm2712-sdhci"]},
            )
        )

    def test_sdio_wifi_child_is_not_mmc_controller(self) -> None:
        self.assertFalse(
            DTB_BOOT_ROOTS.looks_like_mmc(
                "/soc@107c000000/mmc@1100000/wifi@1",
                {"compatible": ["brcm,bcm4329-fmac"]},
            )
        )

    def test_compatible_fallback_still_recognizes_sdhci(self) -> None:
        self.assertTrue(
            DTB_BOOT_ROOTS.looks_like_mmc(
                "/soc@0/storage-controller@1234",
                {"compatible": ["vendor,example-sdhci"]},
            )
        )


if __name__ == "__main__":
    unittest.main()
