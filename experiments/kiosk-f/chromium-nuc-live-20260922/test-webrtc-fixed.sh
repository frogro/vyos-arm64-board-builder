#!/bin/bash
set -euo pipefail
root=$(realpath "${1:?fixtures}"); out=${2:?new results}
browser_image=${3:?browser image}; publisher_image=${4:?FFmpeg image}
video=${5:?decoder video device}; media=${6:?matching media device}
mediamtx=${7:-/usr/local/bin/mediamtx}
[[ $video =~ ^/dev/video[0-9]+$ && -c $video ]]
[[ $media =~ ^/dev/media[0-9]+$ && -c $media ]]
[[ -x $mediamtx ]]
helpers=/config/kiosk-test/chromium-nuc-20260922
seconds=${WEBRTC_SECONDS:-20}
[[ $seconds =~ ^[0-9]+$ && $seconds -ge 1 && $seconds -le 300 ]]
mkdir "$out"; out=$(realpath "$out")
browser=vyarm-webrtc-browser-$$
publisher=vyarm-webrtc-publisher-$$
network=vyarm-webrtc-internal-$$
trap 'podman rm -f "$publisher" >/dev/null 2>&1 || true; podman rm -f "$browser" >/dev/null 2>&1 || true; podman network rm "$network" >/dev/null 2>&1 || true' EXIT
podman network create --internal "$network" >/dev/null
trap 'exit 130' INT
trap 'exit 143' TERM
groups=()
for n in /dev/dri/renderD*; do [[ ! -c $n ]] || groups+=(--group-add "$(stat -c %g "$n")"); done
for codec in h264; do
 podman run -d --name "$browser" --network "$network" --memory 1g -e WEBRTC_SECONDS="$seconds" --user kiosk "${groups[@]}" \
  --device /dev/dri --device "$video" --device "$media" \
  -v "$helpers/runtime-fixed:/candidate-fixed:ro" -e EXTRA_CAPTURE="${EXTRA_CAPTURE:-0}" -e PROBE_PERF=1 \
  -v "$root:/fixtures:ro" -v "$mediamtx:/tmp/mediamtx:ro" \
  -v "$helpers/webrtc-probe-fixed.py:/probe.py:ro" \
  -v "$helpers/wayland.sh:/probe-wayland.sh:ro" \
  --entrypoint bash "$browser_image" /fixtures/browser-start.sh "$codec" > "$out/$codec-container-id"
 podman run -d --name "$publisher" --network "container:$browser" --memory 256m -v "$root:/fixtures:ro" \
  "$publisher_image" \
  -hide_banner -nostdin -loglevel warning -re -r 60 -i "/fixtures/test-long.$codec" -an -c:v copy -f rtsp -rtsp_transport tcp rtsp://127.0.0.1:18554/probe > "$out/$codec-publisher-id"
 timeout "$((seconds+40))" podman wait "$browser" > "$out/$codec-exit"
 podman logs "$browser" > "$out/$codec.json" 2> "$out/$codec.stderr"
 podman logs "$publisher" > "$out/$codec-publisher.log" 2>&1
 podman rm -f "$publisher" >/dev/null
 podman rm -f "$browser" >/dev/null
 test "$(cat "$out/$codec-exit")" == 0
done

# Confirm RTP decoding, not just successful HTTP/SDP or process exit.
python3 - "$out" <<'PYTHON'
import json,sys
from pathlib import Path
for codec,mime in [("h264","video/H264")]:
 d=json.loads((Path(sys.argv[1])/(codec+".json")).read_text())["page"]
 assert d["state"]=="ended" and d["width"]==1920 and d["height"]==1080,d.get("error")
 assert "connected" in d["connectionStates"] and d["finalConnectionState"]=="connected"
 assert any(x.get("mimeType")==mime for x in d["stats"])
 assert any(x.get("framesDecoded",0)>=max(1,(d["requestedSeconds"]-2)*50) for x in d["stats"])
PYTHON
