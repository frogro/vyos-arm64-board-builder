#!/usr/bin/env python3
"""Resolve the current hostname before vyos-hostsd updates /etc/hosts."""
import argparse
from pathlib import Path
import re


def patched_source(source):
    matches = list(re.finditer(r'^hosts:[^\n]*$', source, re.M))
    if len(matches) != 1:
        raise RuntimeError('Expected exactly one hosts entry in NSS file/template')
    entry = matches[0]
    body, separator, comment = entry.group().partition('#')
    tokens = body.split()[1:]
    if 'myhostname' in tokens:
        return source
    # Fail closed rather than change unfamiliar NSS action clauses.
    if '[' in body or not tokens or tokens[0] != 'files':
        raise RuntimeError('Unexpected hosts lookup policy; review before modifying')
    tokens.insert(1, 'myhostname')
    replacement = 'hosts:          ' + ' '.join(tokens)
    if separator and comment.strip() != 'myhostname':
        replacement += ' #' + comment
    return source[:entry.start()] + replacement + source[entry.end():]


def patch(rootfs):
    if not any(p.is_file() for base in ('usr/lib', 'lib')
               for p in (rootfs / base).glob('**/libnss_myhostname.so.2')):
        raise RuntimeError('libnss_myhostname.so.2 is required for early hostname resolution')
    paths = [rootfs / 'etc/nsswitch.conf',
             rootfs / 'usr/share/vyos/templates/login/nsswitch.conf.j2',
             rootfs / 'usr/libexec/vyos/init/vyos-router']
    # Login configuration regenerates nsswitch.conf on boot/commit. Patch its
    # source too, even if the installed file was already patched previously.
    # security_reset() also regenerates NSS before loading the configuration.
    # Validate all three writers before modifying any file.
    changes = [(path, patched_source(path.read_text())) for path in paths]
    for path, content in changes:
        path.write_text(content)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rootfs', type=Path, required=True)
    patch(parser.parse_args().rootfs)
