#!/usr/bin/env python3
"""Forward explicitly selected USB evdev devices to existing KVM HID functions.

No text/key logging, no global input discovery, no network input endpoint.
"""
import fcntl
import json
import os
from pathlib import Path
import select
import signal
import struct
import threading
import time

CONFIG = Path('/run/vyos-kvm-over-ip/input.json')
EVENT = struct.Struct('@llHHi')
EVIOCGRAB = 0x40044590
FUNCTIONS = Path('/sys/kernel/config/usb_gadget/vyos-kvm/functions')
MODIFIERS = {29: 0, 42: 1, 56: 2, 125: 3, 97: 4, 54: 5, 100: 6, 126: 7}
KEYS = {1:41, 12:45, 13:46, 14:42, 15:43, 26:47, 27:48, 28:40,
        39:51, 40:52, 41:53, 43:49, 51:54, 52:55, 53:56, 55:85,
        57:44, 58:57, 69:83, 70:71, 71:95, 72:96, 73:97, 74:86,
        75:92, 76:93, 77:94, 78:87, 79:89, 80:90, 81:91, 82:98,
        83:99, 86:100, 87:68, 88:69, 96:88, 98:84, 99:70,
        102:74, 103:82, 104:75, 105:80, 106:79, 107:77, 108:81,
        109:78, 110:73, 111:76, 119:72, 127:101}
for linux, usage in zip(range(2, 12), range(30, 40)):
    KEYS[linux] = usage
for start, letters in ((16, 'qwertyuiop'), (30, 'asdfghjkl'), (44, 'zxcvbnm')):
    for linux, letter in enumerate(letters, start):
        KEYS[linux] = ord(letter) - ord('a') + 4
for linux, usage in zip(range(59, 69), range(58, 68)):
    KEYS[linux] = usage


class Keyboard:
    def __init__(self):
        self.pressed = set()

    def update(self, code, value):
        if value == 2 or code not in KEYS and code not in MODIFIERS:
            return None
        if value:
            self.pressed.add(code)
        else:
            self.pressed.discard(code)
        mods = sum(1 << MODIFIERS[k] for k in self.pressed if k in MODIFIERS)
        keys = sorted(KEYS[k] for k in self.pressed if k in KEYS)
        if len(keys) > 6:
            keys = [1] * 6  # HID ErrorRollOver, never silently lose releases.
        return bytes([mods, 0] + keys + [0] * (6 - len(keys)))


class Mouse:
    def __init__(self):
        self.buttons = 0
        self.dx = self.dy = self.wheel = 0
        self.dirty = False

    def update(self, typ, code, value):
        if typ == 1 and 272 <= code <= 276:
            bit = 1 << (code - 272)
            self.buttons = self.buttons | bit if value else self.buttons & ~bit
            self.dirty = True
        elif typ == 2 and code in (0, 1, 8):
            attr = {0:'dx', 1:'dy', 8:'wheel'}[code]
            setattr(self, attr, max(-32767, min(32767, getattr(self, attr) + value)))
            self.dirty = True
        elif typ == 0 and code == 0 and self.dirty:
            reports = []
            while True:
                delta = [max(-127, min(127, n)) for n in (self.dx, self.dy, self.wheel)]
                reports.append(struct.pack('<Bbbb', self.buttons, *delta))
                self.dx -= delta[0]; self.dy -= delta[1]; self.wheel -= delta[2]
                if not (self.dx or self.dy or self.wheel):
                    break
            self.dirty = False
            return reports
        return []


def input_node(path):
    node = Path(path).resolve(strict=True)
    if not node.parent == Path('/dev/input') or not node.name.startswith('event'):
        raise ValueError('Selected input must resolve to an evdev event device')
    bus = Path('/sys/class/input') / node.name / 'device/id/bustype'
    if int(bus.read_text().strip(), 16) != 3:
        raise ValueError('Only USB input devices may be forwarded')
    return node


def hid_node(kind):
    function = FUNCTIONS / ('hid.keyboard' if kind == 'keyboard' else 'hid.mouse-relative')
    # Resolve through major/minor; hidg numbering changes with composite functions.
    expected = (function / 'dev').read_text().strip()
    for node in Path('/dev').glob('hidg*'):
        stat = node.stat()
        if f'{os.major(stat.st_rdev)}:{os.minor(stat.st_rdev)}' == expected:
            return node
    raise FileNotFoundError('HID function node unavailable')


def write_report(fd, report):
    if not select.select([], [fd], [], 0.25)[1]:
        raise TimeoutError('USB host is not accepting HID reports')
    if os.write(fd, report) != len(report):
        raise OSError('Short HID report write')


class Forwarder:
    def __init__(self, kind, path):
        self.kind, self.path = kind, path
        self.source = self.target = None
        self.model = Keyboard() if kind == 'keyboard' else Mouse()
        try:
            self.node = input_node(path)
            self.source = os.open(str(self.node), os.O_RDONLY | os.O_NONBLOCK)
            self.target_node = hid_node(kind)
            self.target = os.open(str(self.target_node), os.O_WRONLY | os.O_NONBLOCK)
            # Clear stale state before grabbing the physical device.
            self.release()
            fcntl.ioctl(self.source, EVIOCGRAB, 1)
        except Exception:
            self.close()
            raise

    def release(self):
        if self.target is not None:
            write_report(self.target, bytes(8 if self.kind == 'keyboard' else 4))

    def close(self):
        try:
            self.release()
        except (OSError, TimeoutError):
            pass
        for attr in ('source', 'target'):
            fd = getattr(self, attr)
            if fd is not None:
                os.close(fd)  # Closing source releases EVIOCGRAB.
                setattr(self, attr, None)

    def read(self):
        data = os.read(self.source, EVENT.size * 64)
        if not data or len(data) % EVENT.size:
            raise OSError('Input disconnected or incomplete event')
        for _, _, typ, code, value in EVENT.iter_unpack(data):
            if typ == 0 and code == 3:  # SYN_DROPPED: release and reacquire.
                raise OSError('Input event overflow')
            if self.kind == 'keyboard':
                report = self.model.update(code, value) if typ == 1 else None
                reports = [report] if report is not None else []
            else:
                reports = self.model.update(typ, code, value)
            for report in reports:
                write_report(self.target, report)


def main():
    config = json.loads(CONFIG.read_text())
    stopped = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopped.set())
    active = {}
    announced = {}
    retry_at = {}
    try:
        while not stopped.is_set():
            for kind, path in config.items():
                if kind in active or time.monotonic() < retry_at.get(kind, 0):
                    continue
                try:
                    active[kind] = Forwarder(kind, path)
                    message = 'USB input forwarding active: ' + kind
                except (OSError, ValueError, TimeoutError):
                    retry_at[kind] = time.monotonic() + 2
                    message = 'Waiting for selected USB input/host: ' + kind
                if announced.get(kind) != message:
                    print(message, flush=True)
                    announced[kind] = message
            if not active:
                stopped.wait(0.25)
                continue
            ready, _, _ = select.select([f.source for f in active.values()], [], [], 0.5)
            for kind, forwarder in list(active.items()):
                try:
                    if forwarder.source in ready:
                        forwarder.read()
                except (OSError, TimeoutError):
                    forwarder.close()
                    del active[kind]
                    retry_at[kind] = time.monotonic() + 2
    finally:
        for forwarder in active.values():
            forwarder.close()


if __name__ == '__main__':
    main()
