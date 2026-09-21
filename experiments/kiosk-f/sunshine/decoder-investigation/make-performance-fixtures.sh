#!/bin/bash
set -euo pipefail
out=$(realpath "${1:?new output directory}")
mkdir "$out"
for codec in h264 hevc; do
 if [[ $codec == h264 ]]; then
 opts=(-c:v libx264 -preset fast -threads 2 -x264-params bframes=3:keyint=60)
 else
 opts=(-c:v libx265 -preset fast -threads 2 -x265-params pools=1:frame-threads=1:bframes=3:keyint=60 -tag:v hvc1)
 fi
 ffmpeg -hide_banner -y -f lavfi -i testsrc2=size=1920x1080:rate=60 -t 30 "${opts[@]}" -b:v 8M -maxrate 8M -bufsize 8M -pix_fmt yuv420p -color_primaries bt709 -color_trc bt709 -colorspace bt709 -color_range tv "$out/test-$codec.mp4" > "$out/$codec-encode.log" 2>&1
done

cp "$(dirname -- "$0")/browser-decode-probe.html" "$out/"
