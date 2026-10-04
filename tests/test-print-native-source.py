#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('prepare_print',ROOT/'experiments/profile-e/cli/prepare-source.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class NativeSource(unittest.TestCase):
    def test_selection_and_shared_usb_owner(self):
        for e,g in [(False,False),(True,False),(False,True),(True,True)]:
            with self.subTest(e=e,g=g),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);files=m.prepare(root,e,g)
                self.assertEqual((root/'src/conf_mode/service_usb_server.py').exists(),e or g)
                self.assertEqual((root/'src/conf_mode/service_print_server.py').exists(),e)
                self.assertEqual((root/'src/helpers/vyarm-print-supervisor.py').exists(),e)
                self.assertFalse((root/'python/vyos/xml_ref/cache.py').exists())
                self.assertEqual(sum(x.endswith('service_usb_server.py') for x in files),int(e or g))
                if e or g:
                    before={x:(root/x).read_bytes() for x in files}
                    with self.assertRaises(ValueError):m.prepare(root,e,g)
                    self.assertEqual(before,{x:(root/x).read_bytes() for x in files})

if __name__=='__main__':unittest.main()
