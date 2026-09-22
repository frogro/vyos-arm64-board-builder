#!/bin/bash
set -euo pipefail
root=/config/kiosk-test/kernel-test3/physical-20260922
cleanup() { podman rm -f vyarm-physical-probe >/dev/null 2>&1 || true; systemctl start vyos-container-kiosk-test.service; }
trap cleanup EXIT
systemctl stop vyos-container-kiosk-test.service
timeout -k 5 90 podman run --rm --name vyarm-physical-probe --privileged --network none --memory 1g -e VYARM_CAPTURE_EXTRA=0 -e VYARM_CAPTURE_COUNT=0 -e VYARM_DECODER_DEVICE=/dev/video2 -e PROBE_PERF=1 -e PROBE_TIMEOUT=50 -e PROBE_WIDTH=1080 -e PROBE_HEIGHT=1920 -v /config/kiosk-test/kernel-test3/capture-count/capture-count-v3.so:/capture-count-v3.so:ro -v /config/kiosk-test/kernel-test3/physical-20260922/probe.py:/probe.py:ro -v "$root/inside.sh:/inside.sh:ro" -v /config/kiosk-test/kernel-test3/vp9-mail-test/long-fixtures:/fixtures:ro --entrypoint bash localhost/vyarm-kiosk:weston16-test3 /inside.sh vp9 > "$root/vp9.json" 2> "$root/vp9.stderr"
