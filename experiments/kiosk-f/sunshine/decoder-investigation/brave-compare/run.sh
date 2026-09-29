#!/bin/bash
set -euo pipefail
root=/config/kiosk-test/kernel-test3
while systemctl is-active --quiet vyarm-brave-build || systemctl is-active --quiet vyarm-buffer-lifetime; do sleep 2; done
podman run --rm --entrypoint bash localhost/vyarm-kiosk:brave-compare -c 'brave-browser --version; dpkg-query -W brave-browser' > "$root/brave-compare/versions.txt"
PERF_RUNS=1 bash "$root/brave-compare/tools/test-browser-performance.sh" localhost/vyarm-kiosk:brave-compare "$root/browser-perf-fixtures" "$root/brave-compare/results" /dev/video2 /dev/media0
