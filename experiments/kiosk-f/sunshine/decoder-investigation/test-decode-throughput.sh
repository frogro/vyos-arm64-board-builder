#!/bin/bash
set -euo pipefail
image=${1:?image}; fixtures=$(realpath "${2:?fixtures}"); out=${3:?new results}
video=${4:?video}; media=${5:?media}
[[ $video =~ ^/dev/video[0-9]+$ && -c $video ]]
[[ $media =~ ^/dev/media[0-9]+$ && -c $media ]]
mkdir "$out"
name=vyarm-gst-throughput-$$
trap 'podman rm -f "$name" >/dev/null 2>&1 || true' EXIT
for round in 1 2 3; do
 for codec in h264 hevc; do
  element=v4l2slh264dec; parser=h264parse
  [[ $codec != hevc ]] || { element=v4l2slh265dec; parser=h265parse; }
  timeout -k 5 90 podman run --rm --name "$name" --network none --memory 512m --device "$video" --device "$media" -v "$fixtures:/fixtures:ro" "$image" gst-launch-1.0 -e -v filesrc location="/fixtures/test.$codec" ! "$parser" ! "$element" ! fakesink silent=false sync=false > "$out/$round-$codec.log" 2>&1
 done
done
