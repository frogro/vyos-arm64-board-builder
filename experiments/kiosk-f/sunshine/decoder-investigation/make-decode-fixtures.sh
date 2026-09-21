#!/bin/bash
# Synthetic input only; no customer/HDMI recordings.
set -euo pipefail
out=${1:?new output directory required}
mkdir "$out"
for codec in h264 hevc; do
  if [[ $codec == h264 ]]; then
    encoder=(-c:v libx264 -preset fast -threads 2 -x264-params bframes=3:keyint=30)
  else
    encoder=(-c:v libx265 -preset fast -threads 2 -x265-params pools=1:frame-threads=1:bframes=3:keyint=30)
  fi
  ffmpeg -nostdin -v error -f lavfi -i testsrc2=size=1280x720:rate=30 -frames:v 90 \
    "${encoder[@]}" -pix_fmt yuv420p -color_range tv -colorspace bt709 \
    -color_primaries bt709 -color_trc bt709 -f "$codec" "$out/test.$codec"
  ffmpeg -nostdin -v error -i "$out/test.$codec" -pix_fmt yuv420p -f rawvideo "$out/reference-$codec.i420"
done
sha256sum "$out"/* > "$out/SHA256SUMS"
