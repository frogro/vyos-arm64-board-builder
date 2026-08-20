#!/usr/bin/env python3

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parent.parent
DRIVERS = ROOT / "profiles/extended-network-drivers.txt"
MODULES = ROOT / "profiles/extended-network-modules.tsv"
BASELINE = ROOT / "profiles/baseline-network-modules.txt"
SUPPLEMENTS = ROOT / "profiles/extended-network-firmware-supplements.txt"
DOC = ROOT / "docs/extended-network-drivers.md"


def data_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


class ExtendedNetworkProfileTests(unittest.TestCase):
    def test_driver_requests_are_unique_modules(self) -> None:
        symbols = []

        for line in data_lines(DRIVERS):
            match = re.fullmatch(r"(CONFIG_[A-Za-z0-9_]+)=m", line)
            self.assertIsNotNone(match, line)
            symbols.append(match.group(1))

        self.assertEqual(len(symbols), len(set(symbols)))
        self.assertGreaterEqual(len(symbols), 30)

    def test_catalog_is_well_formed_and_references_requests(self) -> None:
        requested = {
            line.split("=", 1)[0] for line in data_lines(DRIVERS)
        }
        categories = set()
        pairs = set()

        for line in data_lines(MODULES):
            parts = line.split("\t")
            self.assertEqual(4, len(parts), line)
            category, symbol, module, family = parts
            self.assertIn(symbol, requested)
            self.assertRegex(module, r"^[A-Za-z0-9_]+$")
            self.assertTrue(family)
            self.assertNotIn((symbol, module), pairs)
            pairs.add((symbol, module))
            categories.add(category.split("-", 1)[0])

        self.assertTrue({"wifi", "wwan", "ethernet"} <= categories)

    def test_stock_and_unsafe_families_are_not_extended(self) -> None:
        driver_text = DRIVERS.read_text(encoding="utf-8")

        for forbidden in (
            "CONFIG_R8169=",
            "CONFIG_USB_RTL8152=",
            "CONFIG_USB_NET_CDC_MBIM=",
            "CONFIG_MHI_BUS_EP=",
            "CONFIG_COMPILE_TEST=",
        ):
            self.assertNotIn(forbidden, driver_text)

        self.assertIn("r8169", data_lines(BASELINE))

    def test_supplements_require_module_scoping(self) -> None:
        for line in data_lines(SUPPLEMENTS):
            module, pattern = line.split("\t")
            self.assertRegex(module, r"^[A-Za-z0-9_]+$")
            self.assertFalse(pattern.startswith("/"))
            self.assertNotIn("..", Path(pattern).parts)

    def test_documentation_covers_policy_and_categories(self) -> None:
        text = DOC.read_text(encoding="utf-8")

        for phrase in (
            "Include common additional network drivers and firmware? [y/N]",
            "Realtek Wi-Fi",
            "MediaTek Wi-Fi",
            "Qualcomm/Atheros Wi-Fi",
            "Intel Wi-Fi",
            "PCIe/M.2 WWAN",
            "Intel Ethernet",
            "Aquantia USB Ethernet",
            "third-party Wi-Fi DKMS",
            "modinfo -F firmware",
        ):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
