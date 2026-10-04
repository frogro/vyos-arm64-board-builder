#!/usr/bin/python3
"""Reconcile only explicitly selected USB printers across device re-enumeration.

This helper is independent of the VyOS configuration library so USB changes do
not require a new commit. A changed serial/identity at the same port is denied.
The CUPS container is recreated to revoke stale device grants (USB bus/device
numbers can be reused for another device). No whole USB bus is mounted.
"""
import argparse
import json
import logging
import signal
import subprocess
import time
from pathlib import Path

LOG = logging.getLogger('vyarm-print')
SYSFS = Path('/sys/bus/usb/devices')
STOP = False


def identity(port, sysfs=SYSFS):
    device = sysfs / port
    try:
        if (device/'authorized').exists() and (device/'authorized').read_text().strip() != '1':
            return None
        return dict(port=port, vendor=(device/'idVendor').read_text().strip(),
                    product=(device/'idProduct').read_text().strip(),
                    serial=(device/'serial').read_text().strip() if (device/'serial').exists() else '')
    except (OSError, ValueError):
        return None


def devices(bindings, sysfs=SYSFS):
    result = []
    for binding in bindings:
        if identity(binding['port'], sysfs) != binding:
            continue
        device = sysfs / binding['port']
        try:
            bus = int((device/'busnum').read_text())
            number = int((device/'devnum').read_text())
            node = f'/dev/bus/usb/{bus:03d}/{number:03d}'
            # Recheck identity after reading the address to avoid a stale match.
            if identity(binding['port'], sysfs) == binding:
                result.append(node)
        except (OSError, ValueError):
            continue
    return tuple(sorted(result))


def command(config, nodes):
    root = Path('/config/profile-e')
    cmd = ['/usr/bin/podman', 'run', '--rm', '--replace', '--name', 'vyarm-print',
           '--network', 'host', '--memory', '512m', '--pids-limit', '256']
    for source, target in [('cups', '/etc/cups'), ('spool', '/var/spool/cups'),
                           ('logs', '/var/log/cups'),
                           ('admin-password', '/run/secrets/printadmin:ro')]:
        cmd += ['-v', str(root/source)+':'+target]
    for node in nodes:
        cmd += ['--device', node]
    return cmd + [config['image']]


def stop_container(child):
    if child is None:
        return
    subprocess.run(['/usr/bin/podman', 'stop', '--ignore', '--time', '10', 'vyarm-print'],
                   timeout=20, check=False)
    try:
        child.wait(timeout=15)
    except subprocess.TimeoutExpired:
        child.terminate()
        child.wait(timeout=5)


def stop(_signum, _frame):
    global STOP
    STOP = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('config', type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    logging.basicConfig(level=logging.INFO)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    child = None
    previous = None
    try:
        while not STOP:
            current = devices(config['bindings'])
            if current != previous:
                stop_container(child)
                child = None
                if STOP:
                    break
                # A USB change during graceful CUPS shutdown must be reflected.
                current = devices(config['bindings'])
                LOG.info('Selected USB device grants: %s', ', '.join(current) or '(none)')
                child = subprocess.Popen(command(config, current))
                previous = current
            elif child is not None and child.poll() is not None:
                raise RuntimeError(f'CUPS container exited with status {child.returncode}')
            time.sleep(0.5)
    finally:
        stop_container(child)


if __name__ == '__main__':
    main()
