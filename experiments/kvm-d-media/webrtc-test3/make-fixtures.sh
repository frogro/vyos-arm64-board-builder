#!/bin/bash
set -euo pipefail
out=$(realpath "${1:?new fixture directory}")
mkdir "$out"
for codec in h264 hevc; do
 if [[ $codec == h264 ]]; then
 opts=(-c:v libx264 -preset fast -threads 2 -tune zerolatency -x264-params bframes=0:keyint=60 -f h264)
 else
 opts=(-c:v libx265 -preset fast -threads 2 -tune zerolatency -x265-params pools=1:frame-threads=1:bframes=0:keyint=60 -f hevc)
 fi
 ffmpeg -hide_banner -y -f lavfi -i testsrc2=size=1920x1080:rate=60 -t 3 "${opts[@]}" -b:v 8M -maxrate 8M -bufsize 8M -pix_fmt yuv420p -color_primaries bt709 -color_trc bt709 -colorspace bt709 -color_range tv "$out/test.$codec" > "$out/$codec.log" 2>&1
done

python3 - "$out" "${FIXTURE_SECONDS:-30}" <<'PYTHON'
from pathlib import Path
import sys
r=Path(sys.argv[1]);seconds=int(sys.argv[2]);assert 3<=seconds<=330
for c in ["h264","hevc"]:(r/("test-long."+c)).write_bytes((r/("test."+c)).read_bytes()*((seconds+2)//3))
PYTHON
cp "$(dirname -- "$0")"/{webrtc-probe.html,mediamtx.yml,browser-start.sh} "$out/"
