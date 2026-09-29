#!/usr/bin/env python3
"""Resolve the current hostname before vyos-hostsd updates /etc/hosts."""
import argparse
from pathlib import Path
import re


def patch(rootfs):
    path = rootfs / 'etc/nsswitch.conf'
    source = path.read_text()
    matches = list(re.finditer(r'^hosts:[^\n]*$', source, re.M))
    if len(matches) != 1:
        raise RuntimeError('Expected exactly one hosts entry in nsswitch.conf')
    if not any(p.is_file() for base in ('usr/lib', 'lib')
               for p in (rootfs / base).glob('**/libnss_myhostname.so.2')):
        raise RuntimeError('libnss_myhostname.so.2 is required for early hostname resolution')
    entry = matches[0]
    body, separator, comment = entry.group().partition('#')
    tokens = body.split()[1:]
    if 'myhostname' in tokens:
        return
    # Do not silently change the meaning of unfamiliar NSS action clauses.
    if '[' in body or not tokens or tokens[0] != 'files':
        raise RuntimeError('Unexpected hosts lookup policy; review before modifying')
    tokens.insert(1, 'myhostname')
    replacement = 'hosts:          ' + ' '.join(tokens)
    if separator:
        replacement += ' #' + comment
    path.write_text(source[:entry.start()] + replacement + source[entry.end():])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rootfs', type=Path, required=True)
    patch(parser.parse_args().rootfs)
