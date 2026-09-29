#!/usr/bin/env python3
"""Do not start rsyslog before native VyOS syslog configuration exists."""
import argparse
from pathlib import Path


def patch(rootfs):
    changes = []
    rules = [
        ('system_timezone.py', "    call('systemctl restart rsyslog')",
         "    call('systemctl try-restart rsyslog')"),
        ('system_host-name.py', "        tmp = systemd_services['syslog']\n        call(f'systemctl restart {tmp}')",
         "        tmp = systemd_services['syslog']\n        call(f'systemctl try-restart {tmp}')"),
    ]
    for filename, old, new in rules:
        target = rootfs / 'usr/libexec/vyos/conf_mode' / filename
        source = target.read_text()
        if new in source and old not in source:
            continue
        if source.count(old) != 1:
            raise RuntimeError(f'Unexpected {filename} implementation; review upstream before patching')
        source = source.replace(old, new)
        compile(source, str(target), 'exec')
        changes.append((target, source))
    # Validate both upstream handlers before changing either file.
    for target, source in changes:
        target.write_text(source)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rootfs', type=Path, required=True)
    patch(parser.parse_args().rootfs)
