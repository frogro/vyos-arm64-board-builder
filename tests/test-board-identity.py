#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]

class IdentityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.dt = self.base / 'dt'
        self.dt.mkdir()
        (self.dt/'model').write_bytes(b'Radxa E52C\0')
        (self.dt/'compatible').write_bytes(b'radxa,e52c\0rockchip,rk3588\0')
        (self.dt/'serial-number').write_bytes(b'012345ABCDEF\0')
        code=(ROOT/'tools/common-firstboot/board_identity.py').read_text().replace('/sys/firmware/devicetree/base', str(self.dt)).replace('/var/lib/dhcpv6/dhcp6c_duid', str(self.base/'duid'))
        self.ns={'__name__':'test'}
        exec(code,self.ns)

    def test_image_recreation_same_serial_same_duid(self):
        self.ns['ensure_duid']()
        first=(self.base/'duid').read_bytes()
        (self.base/'duid').unlink()
        self.ns['ensure_duid']()
        self.assertEqual(first,(self.base/'duid').read_bytes())
        self.assertEqual(first,struct.pack('=H',18)+b'\0\4'+uuid.uuid5(uuid.NAMESPACE_DNS,'012345ABCDEF').bytes)

    def test_existing_identity_retained(self):
        b=struct.pack('=H',18)+b'\0\4'+uuid.uuid4().bytes
        (self.base/'duid').write_bytes(b)
        self.ns['ensure_duid']()
        self.assertEqual((self.base/'duid').read_bytes(),b)

    def test_no_serial_no_invented_identity(self):
        (self.dt/'serial-number').unlink()
        self.assertNotIn('hardware_uuid',self.ns['hardware']())
        with self.assertRaises(RuntimeError):self.ns['ensure_duid']()
        self.assertFalse((self.base/'duid').exists())

    def test_other_board_not_enabled(self):
        (self.dt/'model').write_bytes(b'Radxa ROCK 5B\0')
        (self.dt/'compatible').write_bytes(b'radxa,rock-5b\0')
        with self.assertRaises(RuntimeError):self.ns['hardware']()

    def test_bad_existing_file_not_overwritten(self):
        (self.base/'duid').write_bytes(b'bad')
        with self.assertRaises(RuntimeError):self.ns['ensure_duid']()
        self.assertEqual((self.base/'duid').read_bytes(),b'bad')

if __name__=='__main__':unittest.main()
