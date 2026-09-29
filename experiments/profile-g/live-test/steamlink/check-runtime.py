#!/usr/bin/env python3
"""Fail closed before enabling the ABI/offset-specific Steam decoder experiment."""
import argparse
import hashlib
from pathlib import Path
import sys

EXPECTED = {
    'shell': 'b245adfccc2cda43e405194cd66615c30ffdae6f7416b7db0579d5c161a3f7fd',
    'libavcodec.so.61': '0b02162ff04a2ed18b0cc4e558bdc8922da907dc595a5450b5d46530c71e1eb0',
    'libavutil.so.59': '0b0eecb17fbaf87b79c94dfafe590d11b90d2342e7af0ed70d37f5b148dce280',
}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--shell', type=Path, required=True)
    ap.add_argument('--library-dir', type=Path, required=True)
    args = ap.parse_args()
    for name, expected in EXPECTED.items():
        path = args.shell if name == 'shell' else args.library_dir / name
        try:
            with path.open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        except OSError as exc:
            print(f'Steam hardware experiment refused: {name}: {exc}', file=sys.stderr)
            return 1
        if actual != expected:
            print(f'Steam hardware experiment refused: unexpected {name} SHA256 {actual}', file=sys.stderr)
            return 1
    print('Steam experimental decoder runtime: exact binary and FFmpeg hashes verified')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
