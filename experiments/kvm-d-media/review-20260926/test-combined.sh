#!/bin/bash
set -euo pipefail
OUT=/tmp/d-review-20260926
P=/sys/module/rockchip_rga/parameters/experimental_full_csc
[[ $(cat "$P") == N ]]
systemd-run --unit=d-rga-combined-restore --on-active=90s "$OUT/restore.sh"
trap '"$OUT/restore.sh"; systemctl stop d-rga-combined-restore.timer' EXIT
printf 'Y\n' > "$P"
timeout -k 5 40 gst-launch-1.0 -q videotestsrc num-buffers=300 ! video/x-raw,format=BGR,width=1920,height=1080,framerate=60/1,colorimetry=sRGB ! v4l2convert ! video/x-raw,format=NV12,colorimetry=bt709 ! mpph264enc bps=8000000 gop=60 ! h264parse ! filesink location="$OUT/combined.h264" > "$OUT/combined.log" 2>&1
ffprobe -v error -count_frames -show_entries stream=codec_name,width,height,nb_read_frames,color_range,color_space,color_primaries,color_transfer -of json "$OUT/combined.h264" > "$OUT/combined.json"
cat "$OUT/combined.json"
