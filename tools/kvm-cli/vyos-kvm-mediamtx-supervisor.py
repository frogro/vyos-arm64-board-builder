#!/usr/bin/env python3
"""Keep MoQ certificates off an unsynchronized clock; leave RTSP/WebRTC usable."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def synchronized():
    try:
        return subprocess.run(['chronyc', 'waitsync', '1', '0.1'],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              timeout=3).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def decision(requested, enabled, synced, clock_jump):
    if not requested:
        return False
    if clock_jump:
        return synced
    return enabled or synced


def main(config):
    requested = 'moq: true' in Path(config).read_text().splitlines()
    child = None
    stopping = False
    def stop(signum, frame):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    def terminate():
        if child and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
    enabled = False
    wall, mono = time.time(), time.monotonic()
    try:
        while not stopping:
            now, tick = time.time(), time.monotonic()
            jumped = abs((now-wall)-(tick-mono)) > 5
            wall, mono = now, tick
            ready = synchronized() if requested and (not enabled or jumped) else False
            desired = decision(requested, enabled, ready, jumped)
            if child is not None and child.poll() is not None:
                return child.returncode or 1
            if child is None or desired != enabled or (requested and jumped):
                terminate()
                if stopping:
                    break
                if requested and jumped:
                    # Only our ephemeral auto-generated page certificate.
                    Path('auto.key').unlink(missing_ok=True)
                    Path('auto.crt').unlink(missing_ok=True)
                enabled = desired
                env = os.environ.copy()
                env['MTX_MOQ'] = 'true' if enabled else 'false'
                print('MediaMTX: MoQ ' + ('enabled (clock synchronized)' if enabled else
                      'disabled' + (' (waiting for Chrony)' if requested else '')), flush=True)
                child = subprocess.Popen(['/usr/local/bin/mediamtx', config], env=env)
            time.sleep(2)
    finally:
        terminate()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
