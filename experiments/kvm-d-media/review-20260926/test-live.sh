#!/bin/bash
set -euo pipefail
OUT=/tmp/d-review-20260926
mkdir -p "$OUT"
P=/sys/module/rockchip_rga/parameters/experimental_full_csc
old=$(cat "$P")
printf '#!/bin/sh\nprintf "%%s\\n" "%s" > %s\n' "$old" "$P" > "$OUT/restore.sh"
chmod 700 "$OUT/restore.sh"
systemd-run --unit=d-rga-review-restore --on-active=120s "$OUT/restore.sh"
trap '"$OUT/restore.sh"; systemctl stop d-rga-review-restore.timer' EXIT
python3 /tmp/d-colors-20260926.py > "$OUT/rga-before.json" || true
printf 'Y\n' > "$P"
python3 /tmp/d-colors-20260926.py > "$OUT/rga-enabled.json" || true
"$OUT/restore.sh"
for codec in h264 hevc; do
 timeout -k 5 25 /usr/local/bin/ffmpeg-rockchip -hide_banner -nostdin -y -f lavfi -i testsrc2=size=1920x1080:rate=60 -frames:v 120 -vf format=nv12 -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 -c:v "${codec}_rkmpp" -b:v 8M -g 60 -f "$codec" "$OUT/$codec.$codec" > "$OUT/$codec.log" 2>&1 || true
 ffprobe -v error -count_frames -show_entries stream=codec_name,width,height,nb_read_frames,color_range,color_space,color_primaries,color_transfer -of json "$OUT/$codec.$codec" > "$OUT/$codec.json" 2> "$OUT/$codec-probe.log" || true
done
 timeout -k 5 25 gst-launch-1.0 -q videotestsrc num-buffers=120 ! video/x-raw,format=NV12,width=1920,height=1080,framerate=60/1,colorimetry=bt709 ! mpph264enc bps=8000000 gop=60 ! h264parse ! filesink location="$OUT/gst.h264" > "$OUT/gst.log" 2>&1 || true
ffprobe -v error -count_frames -show_entries stream=codec_name,width,height,nb_read_frames,color_range,color_space,color_primaries,color_transfer -of json "$OUT/gst.h264" > "$OUT/gst.json" 2> "$OUT/gst-probe.log" || true
cat "$OUT"/*.json
