#!/bin/bash
set -euo pipefail
codec=${1:?codec}; fixtures=${2:?fixtures}; label=${3:?label}; extra=${4:-0}; video=${5:-}; media=${6:-}
root=/config/kiosk-test/chromium-nuc-20260922
out="$root/results/$label"
mkdir -p "$root/results"
[[ ! -e "$out.json" ]]
name=vyarm-nuc-chromium-test
trap 'podman rm -f "$name" >/dev/null 2>&1 || true' EXIT
args=()
for node in /dev/dri/renderD*; do [[ ! -c $node ]] || args+=(--group-add "$(stat -c %g "$node")"); done
if [[ -n $video ]]; then args+=(--device "$video" --device "$media"); fi
timeout -k 5 180 podman run --rm --name "$name" --network none --memory 1500m --shm-size 256m \
 --user kiosk "${args[@]}" --device /dev/dri \
 -e EXTRA_AV1_CAPTURE="${EXTRA_AV1_CAPTURE:-0}" -e PROBE_DEBUG="${PROBE_DEBUG:-0}" -e PROBE_BROWSER="${PROBE_BROWSER:-/candidate/chrome}" -e PROBE_SOFTWARE="${PROBE_SOFTWARE:-0}" -e EXTRA_CAPTURE="$extra" -e PROBE_TIMEOUT="${PROBE_TIMEOUT:-150}" -e PROBE_PERF="${PROBE_PERF:-1}" \
 -e PROBE_WIDTH=1920 -e PROBE_HEIGHT=1080 \
 -v "$root/runtime:/candidate:ro" -v "$root/runtime-fixed:/candidate-fixed:ro" -v "$fixtures:/fixtures:ro" \
 -v "$root/probe-v3.py:/probe.py:ro" -v "$root/wayland.sh:/probe-wayland.sh:ro" \
 --entrypoint bash localhost/vyarm-kiosk:weston16-test3 /probe-wayland.sh "$codec" > "$out.json" 2> "$out.stderr"
