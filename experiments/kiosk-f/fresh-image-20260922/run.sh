#!/bin/bash
set -eu
root=/tmp/vyarm-fresh-decode-20260922
codec=$1
video=/dev/video2
[[ $codec != av1 ]] || video=/dev/video5
timeout -k 5 90 podman run --rm --name fresh-decoder-test --network none --memory 1500m --shm-size 256m --user kiosk --group-add 44 --group-add "$(stat -c %g /dev/dri/renderD128)" --device /dev/dri --device "$video" --device /dev/media0 --device /dev/media1 --device /dev/media2 --device /dev/media3 -e PROBE_BROWSER=/opt/vyarm/chromium/chrome -e KIOSK_VIDEO_DECODE=auto -e KIOSK_VIDEO_H264_BUFFERS=enabled -e KIOSK_VIDEO_AV1_BUFFERS=enabled -e PROBE_PERF=1 -e PROBE_TIMEOUT=45 -v "$root/fixtures:/fixtures:ro" -v "$root/probe.py:/probe.py:ro" -v "$root/wayland.sh:/probe-wayland.sh:ro" --entrypoint bash localhost/vyarm-kiosk:full-f-20260922 /probe-wayland.sh "$codec" > "$root/$codec.json" 2> "$root/$codec.stderr"
