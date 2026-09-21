#!/bin/bash
# Explicit decoder devices must be identified through the host media graph first.
set -euo pipefail
image=${1:?image}; fixtures=$(realpath "${2:?fixtures}"); out=${3:?new output directory}
video=${4:?decoder video device}; media=${5:?matching media device}
[[ $video =~ ^/dev/video[0-9]+$ && -c $video ]]
[[ $media =~ ^/dev/media[0-9]+$ && -c $media ]]
root=$(cd -- "$(dirname -- "$0")" && pwd)
mkdir "$out"; out=$(realpath "$out")
name=vyarm-browser-wayland-$$
trap 'podman rm -f "$name" >/dev/null 2>&1 || true' EXIT INT TERM
# Existing render nodes, not a board-name lookup. Keep Chromium sandbox enabled.
groups=()
for node in /dev/dri/renderD*; do
 [[ -c $node ]] && groups+=(--group-add "$(stat -c %g "$node")")
done
for codec in h264 hevc; do
 timeout -k 5 60 podman run --rm --name "$name" --network none --memory 1g \
  --user kiosk "${groups[@]}" --device /dev/dri --device "$video" --device "$media" \
  -v "$fixtures:/fixtures:ro" -v "$root/browser-device-probe.py:/probe.py:ro" \
  -v "$root/probe-wayland.sh:/probe-wayland.sh:ro" --entrypoint bash \
  "$image" /probe-wayland.sh "$codec" > "$out/$codec.json" 2> "$out/$codec.stderr"
done
# Inspect Media diagnostics and frame correctness: process exit0 alone is not PASS.
