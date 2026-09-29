#!/usr/bin/env python3
"""Bounded host-side Sunshine evdev bridge. Experimental; no saved config writes.

Only forwards devices obtained from the selected Sunshine process's uinput FDs.
The target must already have cgroup permission for evdev. No CAP_MKNOD in target.
"""
import argparse
import ctypes
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import socket
import stat
import struct
import subprocess
import time

LIBC = ctypes.CDLL(None, use_errno=True)
ALLOWED = {'libvirtualhid Keyboard', 'libvirtualhid Mouse', 'libvirtualhid Mouse (absolute)',
           'libvirtualhid Mouse (Absolute)'}


def run(*args, **kw):
    return subprocess.run(args, check=True, capture_output=True, timeout=5, **kw).stdout


class ContainerUnavailable(ValueError):
    """The supervised container is stopped or being recreated."""


def container(name):
    try:
        # Generic inspect can resolve the same-named network during recreation.
        info = json.loads(run('podman', 'container', 'inspect', name))[0]
    except subprocess.CalledProcessError as error:
        if b'no such container' in (error.stderr or b'').lower():
            raise ContainerUnavailable('Container is absent') from error
        raise
    if not info.get('State', {}).get('Running'):
        raise ContainerUnavailable('Container is not running')
    return info['Id'], int(info['State']['Pid'])


def sunshine_pids(name):
    rows = run('podman', 'top', name, 'hpid', 'comm').decode().splitlines()[1:]
    return [int(row.split()[0]) for row in rows if row.split()[1:] == ['sunshine']]


def owned_inputs(pid):
    """Never infer ownership from a matching input name alone."""
    result = {}
    pidfd = os.pidfd_open(pid)
    try:
        for entry in Path(f'/proc/{pid}/fd').iterdir():
            try:
                if os.readlink(entry) != '/dev/uinput':
                    continue
                fd = LIBC.syscall(438, pidfd, int(entry.name), 0)  # pidfd_getfd, arm64/x86_64
                if fd < 0:
                    raise OSError(ctypes.get_errno(), 'pidfd_getfd')
                try:
                    value = bytearray(128)
                    fcntl.ioctl(fd, 0x8080552c, value, True)  # UI_GET_SYSNAME(128)
                    sysname = bytes(value).split(b'\0')[0].decode()
                finally:
                    os.close(fd)
                if not re.fullmatch(r'input[0-9]+', sysname):
                    continue
                base = Path('/sys/devices/virtual/input') / sysname
                if base.is_symlink() or not base.is_dir() or (base / 'name').read_text().strip() not in ALLOWED:
                    continue
                for event in base.glob('event[0-9]*'):
                    if not re.fullmatch(r'event[0-9]+', event.name):
                        continue
                    major, minor = map(int, (event / 'dev').read_text().split(':'))
                    if major == 13:
                        result[event.name] = (str(event), os.makedev(major, minor))
            except FileNotFoundError:
                continue
    finally:
        os.close(pidfd)
    return result


def properties(data):
    if not data.startswith(b'libudev\0') or len(data) < 40:
        return {}
    offset, length = struct.unpack_from('=II', data, 16)
    if offset < 40 or offset + length > len(data):
        return {}
    return dict(item.split(b'=', 1) for item in data[offset:offset+length].split(b'\0') if b'=' in item)


def removal(data):
    """Reuse actual udev header/filter hashes; update variable property length."""
    offset, length = struct.unpack_from('=II', data, 16)
    values = data[offset:offset+length].split(b'\0')
    values = [b'ACTION=remove' if v.startswith(b'ACTION=') else v for v in values]
    body = b'\0'.join(values)
    header = bytearray(data[:offset])
    struct.pack_into('=I', header, 20, len(body))
    return bytes(header) + body


def forward(pid, data):
    run('nsenter', f'--net=/proc/{pid}/ns/net', '--', 'python3', '-c',
        'import socket,sys;s=socket.socket(socket.AF_NETLINK,socket.SOCK_RAW,15);s.bind((0,0));s.sendto(sys.stdin.buffer.read(),(0,2))', input=data)


def control_enabled(name):
    """Fail closed; the installed service has no cross-container source override."""
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,62}', name):
        return False
    try:
        policy = json.loads((Path('/run/vyos-kiosk') / name / 'sunshine.json').read_text())
        info = json.loads(run('podman', 'inspect', name))[0]
        env = info.get('Config', {}).get('Env', [])
        return (policy.get('version') == 1 and policy.get('access') == 'enabled'
                and policy.get('input') == 'control'
                and 'KIOSK_DISPLAY_BACKEND=wayland' in env)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--target', required=True)
    ap.add_argument('--source')
    ap.add_argument('--managed', action='store_true', help='Use native policy and same-container Sunshine only')
    ap.add_argument('--duration', type=int, default=120)
    args = ap.parse_args()
    if args.managed and args.source:
        ap.error('managed mode cannot override source')
    args.source = args.source or args.target
    if not 1 <= args.duration <= 600:
        ap.error('duration must be 1..600 seconds')
    try:
        target = container(args.target)
        source = target if args.source == args.target else container(args.source)
    except ContainerUnavailable:
        if args.managed:
            return  # systemd retries when the native container returns.
        raise
    sock = socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, 15)
    sock.bind((0, 2))
    sock.settimeout(1.0)
    tracked = {}
    stop = False
    def finish(*_):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGTERM, finish)
    signal.signal(signal.SIGINT, finish)
    root = Path(f'/proc/{target[1]}/root/dev/input')
    deadline = float('inf') if args.managed else time.monotonic() + args.duration
    def clean(name):
        node, dev, packet = tracked.pop(name)
        try:
            if container(args.target) != target:
                return
            if packet:
                forward(target[1], removal(packet))
            info = node.lstat()
            if stat.S_ISCHR(info.st_mode) and info.st_rdev == dev:
                node.unlink()
                print(f'Removed {name}', flush=True)
        except (OSError, ValueError, subprocess.CalledProcessError):
            pass
    try:
        while not stop and time.monotonic() < deadline:
            try:
                if container(args.target) != target or (args.source != args.target and container(args.source) != source):
                    break
            except ContainerUnavailable:
                break
            # Bound podman/sysfs polling even when unrelated udev traffic is busy.
            time.sleep(0.8)
            if stop:
                break
            wanted = {}
            if not args.managed or control_enabled(args.target):
                try:
                    pids = sunshine_pids(args.source)
                except subprocess.CalledProcessError:
                    try:
                        container(args.source)
                    except ContainerUnavailable:
                        break
                    raise
                for pid in pids:
                    wanted.update(owned_inputs(pid))
            for name in list(tracked):
                if name not in wanted or tracked[name][1] != wanted[name][1]:
                    clean(name)
            for name, (syspath, dev) in wanted.items():
                if name in tracked:
                    continue
                node = root / name
                # Refuse pre-existing nodes, including symlinks and physical devices.
                if os.path.lexists(node):
                    continue
                os.mknod(node, stat.S_IFCHR | 0o600, dev)
                tracked[name] = (node, dev, None)
                run('udevadm', 'trigger', '--action=add', syspath)
                print(f'Added owned {name}', flush=True)
            try:
                data = sock.recv(65536)
            except socket.timeout:
                continue
            props = properties(data)
            name = props.get(b'DEVNAME', b'').decode().removeprefix('/dev/input/')
            if name in tracked and name in wanted and props.get(b'ACTION') == b'add':
                if props.get(b'DEVPATH', b'').decode() != wanted[name][0].removeprefix('/sys'):
                    continue
                forward(target[1], data)
                node, dev, _ = tracked[name]
                tracked[name] = (node, dev, data)
                print(f'Forwarded add {name}', flush=True)
    finally:
        for name in list(tracked):
            clean(name)
        sock.close()

if __name__ == '__main__':
    main()
