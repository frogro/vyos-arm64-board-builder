#!/usr/bin/env python3
"""Guard A hardware ownership and the optional network/BT boundary."""
import itertools
import subprocess
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class BaseHardware(unittest.TestCase):
    def selection(self, board, network, kvm):
        script = 'source lib/board-hardware.sh; board_hardware_select "$1"; printf "%s\\n" "$BOARD_BASE_CONFIG" "$BOARD_BASE_READY" "$BOARD_BASE_MODULES" "$BOARD_BASE_PATCHES" "$BOARD_PERIPHERAL_PATCHES"'
        return subprocess.check_output(['bash','-eu','-c',script,'test',board], cwd=ROOT,
            env={'PATH':'/usr/bin:/bin','EXTENDED_NETWORK':network,'KVM_OVER_IP':kvm},text=True).splitlines()

    def test_hardware_independent_of_network_and_apps(self):
        for board in ['rock-5b','orangepi5-plus','raspberry-pi-5','radxa-e52c','unknown']:
            expected = self.selection(board,'no','no')
            for network,kvm in itertools.product(['yes','no'],repeat=2):
                self.assertEqual(expected,self.selection(board,network,kvm))
            for path in expected:
                if path:self.assertTrue((ROOT/path).exists(),path)
            if board in ['raspberry-pi-5','radxa-e52c','unknown']:
                self.assertTrue(all(not v for v in expected))

    def test_optional_card_stays_network(self):
        network=(ROOT/'profiles/extended-network-drivers.txt').read_text()
        self.assertIn('CONFIG_RTW89_8852BE=m',network)
        self.assertIn('CONFIG_BT_HCIBTUSB=m',network)
        for p in (ROOT/'profiles/base-hardware').glob('*.config'):
            self.assertNotIn('CONFIG_RTW89_',p.read_text(),str(p))
            self.assertNotIn('CONFIG_BT_',p.read_text(),str(p))
        for symbol in ['CONFIG_SPI_SPIDEV','CONFIG_USB_F_HID','CONFIG_IR_GPIO_CIR']:
            self.assertNotIn(symbol+'=',network)
            self.assertIn(symbol+'=',(ROOT/'profiles/base-hardware/optional-peripherals.config').read_text())

    def test_patch_and_firmware_scope(self):
        rock=self.selection('rock-5b','no','no')
        orange=self.selection('orangepi5-plus','no','no')
        self.assertEqual(rock[3],orange[3])
        self.assertTrue(rock[4].endswith('/rock-5b'))
        self.assertTrue(orange[4].endswith('/orangepi5-plus'))
        self.assertIn('panthor',(ROOT/orange[2]).read_text())
        registry=(ROOT/'profiles/kvm-hardware-providers.conf').read_text()
        self.assertIn('rock5b-fc400000-peripheral.dts',registry)
        for line in registry.splitlines():
            if line.startswith('orangepi5-plus|'):
                self.assertNotIn('rock5b-fc400000', line)
                self.assertEqual('runtime', line.split('|')[5])

    def test_legacy_d_config_uses_same_hardware_requirements(self):
        self.assertEqual((ROOT/'profiles/kvm-over-ip.config').resolve(),
                         ROOT/'profiles/base-hardware/capture-gadget.config')

if __name__=='__main__':unittest.main()
