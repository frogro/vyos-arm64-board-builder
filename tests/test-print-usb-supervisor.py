#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('supervisor', ROOT/'experiments/profile-e/cli/cups-supervisor.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class UsbAssignments(unittest.TestCase):
    def test_replug_and_unrelated_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            printer = root/'4-1.2'
            printer.mkdir()
            values = dict(idVendor='1343', idProduct='0005', serial='RX1-test', busnum='4', devnum='6')
            for key, value in values.items():
                (printer/key).write_text(value)
            binding = module.identity('4-1.2', root)
            self.assertEqual(module.devices([binding], root), ('/dev/bus/usb/004/006',))
            (printer/'devnum').write_text('9')
            self.assertEqual(module.devices([binding], root), ('/dev/bus/usb/004/009',))
            (printer/'authorized').write_text('0')
            self.assertEqual(module.devices([binding], root), ())
            (printer/'authorized').write_text('1')
            (printer/'serial').write_text('another-RX1')
            self.assertEqual(module.devices([binding], root), ())
            (printer/'serial').write_text('RX1-test')
            (printer/'idProduct').write_text('0006')
            self.assertEqual(module.devices([binding], root), ())
            (printer/'idProduct').unlink()
            self.assertEqual(module.devices([binding], root), ())
    def test_grants_only_selected_nodes_without_privileged_container(self):
        cmd = module.command({'image':'localhost/vyarm-print:test'}, ('/dev/bus/usb/004/009',))
        self.assertNotIn('--privileged', cmd)
        self.assertEqual(cmd.count('--device'), 1)
        self.assertNotIn('/dev/bus/usb:/dev/bus/usb', cmd)
        self.assertEqual(cmd[-1], 'localhost/vyarm-print:test')
        self.assertNotIn('--device', module.command({'image':cmd[-1]}, ()))

if __name__ == '__main__':
    unittest.main()
