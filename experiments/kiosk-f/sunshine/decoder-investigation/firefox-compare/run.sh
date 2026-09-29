#!/bin/bash
set -euo pipefail
root=/config/kiosk-test/kernel-test3/firefox-compare
while systemctl is-active --quiet vyarm-pacing-singles; do sleep 2; done
podman run --rm --entrypoint bash localhost/vyarm-kiosk:firefox-compare -c 'firefox-esr --version; dpkg-query -W firefox-esr libavcodec61' > "$root/versions.txt" 2>&1
mkdir -p "$root/results"
name=vyarm-firefox-probe
trap 'podman rm -f "$name" >/dev/null 2>&1 || true' EXIT
for enabled in 0 1; do
 for codec in h264 hevc; do
  timeout -k 5 85 podman run --rm --name "$name" --network none --memory 1g --user kiosk --group-add "$(stat -c %g /dev/dri/renderD128)" --device /dev/dri --device /dev/video2 --device /dev/media0 -e FIREFOX_V4L2="$enabled" -e PROBE_WIDTH=1920 -e PROBE_HEIGHT=1080 -v /config/kiosk-test/kernel-test3/browser-perf-fixtures:/fixtures:ro -v "$root/probe.py:/probe.py:ro" -v "$root/wayland.sh:/wayland.sh:ro" --entrypoint bash localhost/vyarm-kiosk:firefox-compare /wayland.sh "$codec" > "$root/results/$enabled-$codec.json" 2> "$root/results/$enabled-$codec.stderr"
 done
done
