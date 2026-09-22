#!/usr/bin/env python3
"""Do not start rsyslog before native VyOS syslog configuration exists."""
import argparse
from pathlib import Path


def patch(rootfs):
    target = rootfs / 'usr/libexec/vyos/conf_mode/system_timezone.py'
    source = target.read_text()
    old = "    call('systemctl restart rsyslog')"
    new = "    call('systemctl try-restart rsyslog')"
    if new in source and old not in source:
        return
    if source.count(old) != 1:
        raise RuntimeError('Unexpected timezone implementation; review upstream before patching')
    source = source.replace(old, '    # Syslog config is generated later during boot; only restart a running daemon.\n' + new)
    compile(source, str(target), 'exec')
    target.write_text(source)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rootfs', type=Path, required=True)
    patch(parser.parse_args().rootfs)
