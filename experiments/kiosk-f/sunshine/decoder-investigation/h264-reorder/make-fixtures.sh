#!/bin/bash
set -euo pipefail
destination=${1:?new fixture directory}
probe=${2:?browser-decode-probe.html}
probe=$(realpath "$probe")
mkdir "$destination"
cd "$destination"
for variant in b1 b3-no-pyramid b3-ref1; do
 mkdir -p "$variant"
 case "$variant" in
 b1) params=bframes=1:keyint=60;;
 b3-no-pyramid) params=bframes=3:b-pyramid=none:keyint=60;;
 b3-ref1) params=bframes=3:ref=1:keyint=60;;
 esac
 ffmpeg -hide_banner -nostdin -n -f lavfi -i testsrc2=size=1920x1080:rate=60 -t 30 -c:v libx264 -preset fast -threads 2 -x264-params "$params" -b:v 8M -maxrate 8M -bufsize 8M -pix_fmt yuv420p -color_primaries bt709 -color_trc bt709 -colorspace bt709 -color_range tv "$variant/test-h264.mp4" > "$variant/encode.log" 2>&1
 cp "$probe" "$variant/"
 ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,profile,width,height,has_b_frames,refs,r_frame_rate,nb_frames,bit_rate -of json "$variant/test-h264.mp4" > "$variant/metadata.json"
done
