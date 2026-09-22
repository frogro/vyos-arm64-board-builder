# Device Tree fallback validated on Radxa E52C.

from pathlib import Path
import struct
import uuid
import re

def dt(name):
    p = Path('/sys/firmware/devicetree/base') / name
    return p.read_bytes().rstrip(b'\0').decode('ascii').strip() if p.exists() else ''

def valid_serial(serial):
    return bool(re.fullmatch(r'[A-Za-z0-9._:-]{4,128}', serial)) and serial.lower() not in ('unknown', 'none', 'null', 'default', '0123456789', '1234567890') and len(set(serial.replace('-', '').replace(':', ''))) > 1

def hardware():
    model = dt('model')
    compatible = dt('compatible').split('\0')
    if 'radxa,e52c' not in compatible and 'radxa,e52c' not in model.lower() and not ('radxa' in model.lower() and 'e52c' in model.lower()):
        raise RuntimeError('Not an identified Radxa E52C')
    serial = dt('serial-number')
    result = {'hardware_vendor': 'Radxa', 'hardware_model': model}
    if valid_serial(serial):
        result['hardware_serial'] = serial
    return result

def ensure_duid():
    p = Path('/var/lib/dhcpv6/dhcp6c_duid')
    if p.exists():
        b = p.read_bytes()
        if len(b) < 5 or struct.unpack('=H', b[:2])[0] != len(b)-2 or int.from_bytes(b[2:4], 'big') not in (1,2,3,4) or (b[2:4] == b'\x00\x04' and len(b) != 20):
            raise RuntimeError('Existing DUID format unexpected; refusing to overwrite it')
        return 'Existing DUID retained unchanged'
    serial = hardware().get('hardware_serial', '')
    if not valid_serial(serial):
        raise RuntimeError('No usable Device Tree serial; no DUID generated')
    # Same UUIDv5 DNS namespace/name mapping as upstream uuidgen --sha1 --namespace @dns --name SERIAL.
    payload = b'\x00\x04' + uuid.uuid5(uuid.NAMESPACE_DNS, serial).bytes
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('xb') as f:
        f.write(struct.pack('=H', len(payload)) + payload)
    p.chmod(0o600)
    return 'DUID-UUID derived from Device Tree serial (not presented as hardware UUID)'

if __name__ == '__main__':
    print(ensure_duid())
