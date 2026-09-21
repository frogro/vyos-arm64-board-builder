#!/bin/bash
# Compare whole disposable browser/compositor cgroup, not decoder-only CPU.
set -euo pipefail
image=${1:?image}; fixtures=$(realpath "${2:?fixtures}"); out=${3:?new output directory}
video=${4:?decoder video device}; media=${5:?matching media device}
[[ $video =~ ^/dev/video[0-9]+$ && -c $video ]]
[[ $media =~ ^/dev/media[0-9]+$ && -c $media ]]
root=$(cd -- "$(dirname -- "$0")" && pwd)
mkdir "$out"; out=$(realpath "$out")
name=vyarm-browser-perf-$$
trap 'podman rm -f "$name" >/dev/null 2>&1 || true' EXIT INT TERM
groups=()
for node in /dev/dri/renderD*; do
 [[ -c $node ]] && groups+=(--group-add "$(stat -c %g "$node")")
done
# Alternate ordering; six independent processes/profiles, no startup reused.
for run in $(seq 1 "${PERF_RUNS:-3}"); do
 codecs=(h264 hevc); [[ $run != 2 ]] || codecs=(hevc h264)
 for codec in "${codecs[@]}"; do
  cat /sys/class/thermal/thermal_zone*/temp > "$out/$run-$codec-temperature-before.txt"
  timeout -k 5 90 podman run --rm --name "$name" --network none --memory 1g \
   --user kiosk "${groups[@]}" --device /dev/dri --device "$video" --device "$media" \
   -e PROBE_PACING="${PERF_PACING:-default}" -e PROBE_TIMEOUT=50 -e PROBE_PERF=1 -e PROBE_WIDTH="${PERF_WIDTH:-1920}" -e PROBE_HEIGHT="${PERF_HEIGHT:-1080}" \
   -v "$fixtures:/fixtures:ro" -v "$root/browser-device-probe.py:/probe.py:ro" \
   -v "$root/probe-wayland.sh:/probe-wayland.sh:ro" --entrypoint bash \
   "$image" /probe-wayland.sh "$codec" > "$out/$run-$codec.json" 2> "$out/$run-$codec.stderr"
  cat /sys/class/thermal/thermal_zone*/temp > "$out/$run-$codec-temperature-after.txt"
 done
done
