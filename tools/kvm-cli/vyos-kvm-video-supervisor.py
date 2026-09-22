#!/usr/bin/env python3
"""Supervise HDMI capture; process liveness alone does not imply live video."""
import argparse
import json
import os
import re
import signal
import socket
import subprocess
import threading
import time


def detected_timings(device):
    # Avoid the driver's noisy QUERY_DV_TIMINGS error when no source supplies 5V.
    try:
        power = subprocess.run(['v4l2-ctl', '-d', device, '--get-ctrl=power_present'],
                               capture_output=True, text=True, timeout=3)
        if power.returncode or not re.search(r'power_present:\s*(?:0x0*1|1)\b', power.stdout):
            return None
        result = subprocess.run(['v4l2-ctl', '-d', device, '--query-dv-timings'],
                                capture_output=True, text=True, timeout=3)
        if result.returncode:
            return None
        fields = dict(re.findall(r'^\s*([^:\n]+):\s*(.*?)\s*$', result.stdout, re.M))
        if int(fields.get('Active width', '0')) <= 0 or int(fields.get('Active height', '0')) <= 0:
            return None
        # Compare the clock and porch/sync values, not just the resolution.
        return tuple(sorted(fields.items()))
    except (subprocess.TimeoutExpired, ValueError):
        return None


def same_timings(left, right):
    if left is None or right is None:
        return left == right
    left, right = dict(left), dict(right)
    a, b = left.pop('Pixelclock', ''), right.pop('Pixelclock', '')
    if left != right:
        return False
    try:
        a, b = int(a.split()[0]), int(b.split()[0])
        return abs(a - b) <= max(a, b) * 0.005
    except (ValueError, IndexError):
        return a == b


def transport_ready():
    try:
        with socket.create_connection(('127.0.0.1', 8554), timeout=1):
            return True
    except OSError:
        return False


def stream_healthy():
    try:
        result = subprocess.run([
            '/usr/bin/ffprobe', '-v', 'error', '-rtsp_transport', 'tcp',
            '-read_intervals', '%+1', '-count_packets',
            '-show_entries', 'stream=codec_type,nb_read_packets', '-of', 'json',
            'rtsp://127.0.0.1:8554/kvm'], capture_output=True, text=True, timeout=8)
        return result.returncode == 0 and any(
            s.get('codec_type') == 'video' and int(s.get('nb_read_packets', 0)) > 0
            for s in json.loads(result.stdout).get('streams', []))
    except (subprocess.TimeoutExpired, ValueError, TypeError):
        return False


def stop_child(child):
    if child is None:
        return
    try:
        os.killpg(child.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()


def supervise(device, backend, runner, stopped, *, detect=detected_timings,
              ready=transport_ready, healthy=stream_healthy,
              launch=subprocess.Popen, stop=stop_child, clock=time.monotonic):
    child = None
    active_timing = None
    last_state = None
    check_at = 0
    failures = 0
    uses_rtsp = backend in ('ffmpeg', 'gstreamer')

    def log(state):
        nonlocal last_state
        if state != last_state:
            print('KVM video: ' + state, flush=True)
            last_state = state

    try:
        while not stopped.is_set():
            timing = detect(device)
            if stopped.is_set():
                break
            if child is not None and (child.poll() is not None or not same_timings(timing, active_timing)):
                log('capture exited or HDMI signal changed; releasing capture')
                stop(child)
                child = None
                failures = 0
            if timing is None:
                log('waiting for HDMI signal')
            elif child is None:
                if uses_rtsp and not ready():
                    log('waiting for local RTSP transport')
                else:
                    env = dict(os.environ, KVM_VIDEO_SUPERVISED='1')
                    child = launch([runner], env=env, start_new_session=True)
                    active_timing = timing
                    check_at = clock() + 15  # Allow capture/encoder startup.
                    log('HDMI signal ready; starting capture')
            elif uses_rtsp and clock() >= check_at:
                failures = 0 if healthy() else failures + 1
                check_at = clock() + 10
                if failures >= 2:
                    log('no video packets on two checks; restarting capture')
                    stop(child)
                    child = None
                    failures = 0
            stopped.wait(2)
    finally:
        stop(child)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('device')
    parser.add_argument('backend', choices=['ffmpeg', 'gstreamer', 'ustreamer'])
    parser.add_argument('runner')
    args = parser.parse_args()
    stopped = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopped.set())
    supervise(args.device, args.backend, args.runner, stopped)


if __name__ == '__main__':
    main()
