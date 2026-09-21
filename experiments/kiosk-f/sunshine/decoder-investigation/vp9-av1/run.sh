#!/bin/bash
set -euo pipefail
root=/config/kiosk-test/kernel-test3/vp9-av1
v4l2-ctl -d /dev/video2 --list-formats-out > "$root/decoder-formats.txt"
PERF_RUNS=1 bash "$root/tools/test-browser-performance.sh" localhost/vyarm-kiosk:weston16-test3 "$root/fixtures" "$root/results" /dev/video2 /dev/media0
