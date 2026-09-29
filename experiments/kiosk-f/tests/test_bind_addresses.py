import importlib.util
from pathlib import Path
import unittest
s=importlib.util.spec_from_file_location('waiter',Path(__file__).resolve().parents[1]/'systemd/wait-container-addresses.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class BindAddresses(unittest.TestCase):
    def test_native_port_formats(self):
        text='\n'.join(['PublishPort=192.0.2.7:47998:47998/udp',
                         'PublishPort=[2001:db8::7]:47989:47989/tcp',
                         'PublishPort=127.0.0.1:47990:47990/tcp',
                         'PublishPort=0.0.0.0:80:80/tcp',
                         'PublishPort=[::]:80:80/tcp','PublishPort=80:80/tcp'])
        self.assertEqual(m.addresses(text),{'192.0.2.7','2001:db8::7','127.0.0.1'})
    def test_invalid_explicit_address_fails_closed(self):
        with self.assertRaises(ValueError):m.addresses('PublishPort=wrong:80:80/tcp')
if __name__=='__main__': unittest.main()
