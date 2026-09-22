#!/usr/bin/env python3
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bundle', ROOT / 'tools/install-tailscale.py')
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


def archive(machine=183, symlink=False):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as tar:
        for name in ['tailscale', 'tailscaled']:
            data = bytearray(64)
            data[:6] = b'\x7fELF\x02\x01'
            data[18:20] = machine.to_bytes(2, 'little')
            member = tarfile.TarInfo('tailscale_1.2.4_arm64/' + name)
            if symlink:
                member.type = tarfile.SYMTYPE
                member.linkname = '/etc/passwd'
                tar.addfile(member)
            else:
                member.size = len(data)
                tar.addfile(member, io.BytesIO(data))
        # Unselected members must never be extracted.
        member = tarfile.TarInfo('../../outside')
        member.size = 3
        tar.addfile(member, io.BytesIO(b'bad'))
    return stream.getvalue()


class Tests(unittest.TestCase):
    def test_verified_image_programs_do_not_copy_or_modify_identity(self):
        data = archive()
        calls = []
        def download(url):
            calls.append(url)
            if url.endswith('?mode=json'):
                return json.dumps({'TarballsVersion': '1.2.4', 'Tarballs': {'arm64': 'tailscale_1.2.4_arm64.tgz'}}).encode()
            if url.endswith('.sha256'):
                return hashlib.sha256(data).hexdigest().encode()
            return data
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'root'
            (root / 'etc').mkdir(parents=True)
            state = root / 'config/tailscale/state/tailscaled.state'
            state.parent.mkdir(parents=True)
            state.write_text('retained identity')
            metadata = bundle.install(root, download=download)
            self.assertEqual(metadata['version'], '1.2.4')
            for name in ('tailscale', 'tailscaled'):
                self.assertEqual((root / 'usr/libexec/tailscale' / name).stat().st_mode & 0o777, 0o755)
            self.assertEqual(state.read_text(), 'retained identity')
            self.assertFalse((root / 'config/tailscale/bin').exists())
            self.assertFalse((Path(directory) / 'outside').exists())
            self.assertTrue(calls[0].endswith('?mode=json'))

    def test_bad_checksum_rejected(self):
        with self.assertRaisesRegex(ValueError, 'checksum'):
            bundle.unpack(archive(), '1.2.4', '0' * 64)

    def test_wrong_architecture_and_symlink_rejected(self):
        for data in (archive(machine=62), archive(symlink=True)):
            with self.assertRaises(ValueError):
                bundle.unpack(data, '1.2.4', hashlib.sha256(data).hexdigest())

    def test_profile_gate(self):
        script = (ROOT / 'tools/assemble-board-image.sh').read_text()
        self.assertIn('if [[ "$TAILSCALE_SUBNET_ROUTER" == "yes" ]]; then\n    python3 "$ROOT/tools/install-tailscale.py" "$SQUASH_ROOT"\nfi', script)


if __name__ == '__main__':
    unittest.main()
