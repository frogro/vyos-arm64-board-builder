#!/usr/bin/env python3
"""Keep an identical upstream HEVC header when applying the RK3588 backport.

Unknown header contents or patch formats fail closed. All other hunks remain
unchanged and must still pass patch --fuzz=0.
"""
import argparse
import re
from pathlib import Path

HEADER = 'include/media/v4l2-hevc.h'

def prepare(patch, source):
    if source is None:
        return patch
    pattern = r'^--- /dev/null\n\+\+\+ b/include/media/v4l2-hevc.h\n@@ -0,0 \+1,(\d+) @@\n((?:\+[^\n]*\n)+)'
    matches = list(re.finditer(pattern, patch, re.M))
    if len(matches) != 1:
        raise RuntimeError('HEVC header creation patch changed; review required')
    match = matches[0]
    lines = match.group(2).splitlines(keepends=True)
    expected = ''.join(line[1:] for line in lines)
    if len(lines) != int(match.group(1)) or expected != source:
        raise RuntimeError('Existing HEVC header differs from decoder backport; review required')
    return patch[:match.start()] + patch[match.end():]

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('patch', type=Path)
    parser.add_argument('source_root', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    header = args.source_root / HEADER
    args.output.write_text(prepare(args.patch.read_text(), header.read_text() if header.exists() else None))
