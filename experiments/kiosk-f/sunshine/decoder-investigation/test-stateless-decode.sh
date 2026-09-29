#!/bin/bash
# Root, explicit matching decoder video/media devices; host services untouched.
set -euo pipefail
image=${1:?image required}; fixtures=${2:?fixture directory}; out=${3:?new result directory}
shift 3
[[ $# -ge 2 ]] || { echo 'Provide matching /dev/videoN and /dev/mediaN decoder nodes' >&2; exit 2; }
fixtures=$(realpath "$fixtures")
mkdir "$out"; out=$(realpath "$out")
devices=()
for device in "$@"; do
  [[ "$device" =~ ^/dev/(video|media)[0-9]+$ && -c "$device" ]] || exit 2
  devices+=(--device "$device")
done
name=vyarm-stateless-probe-$$
cleanup() { podman rm -f "$name" >/dev/null 2>&1 || true; }
trap cleanup EXIT INT TERM
for codec in h264 hevc; do
  element=v4l2slh264dec; parser=h264parse
  [[ $codec != hevc ]] || { element=v4l2slh265dec; parser=h265parse; }
  for trial in 1 2 3; do
    timeout --kill-after=5s 60s podman run --rm --name "$name" --network none --memory 512m \
      "${devices[@]}" -v "$fixtures:/fixtures:ro" -v "$out:/results" \
      -e GST_DEBUG=v4l2codecs:4 "$image" gst-launch-1.0 -e \
      filesrc location="/fixtures/test.$codec" ! "$parser" ! "$element" ! \
      videoconvert ! video/x-raw,format=I420 ! \
      filesink location="/results/$codec-$trial.i420" > "$out/$codec-$trial.log" 2>&1
    # Exact reference check, including frame count and order; no soft-decoder fallback.
    cmp "$fixtures/reference-$codec.i420" "$out/$codec-$trial.i420"
    sha256sum "$out/$codec-$trial.i420" >> "$out/decoded.sha256"
    rm "$out/$codec-$trial.i420"
  done
done
