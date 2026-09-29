#!/bin/bash
set -euo pipefail
/tmp/mediamtx /fixtures/mediamtx.yml > /tmp/mediamtx.log 2>&1 &
mtx=$!
trap 'kill "$mtx" 2>/dev/null || true; cat /tmp/mediamtx.log >&2' EXIT
seconds=${WEBRTC_SECONDS:-20}
[[ $seconds =~ ^[0-9]+$ && $seconds -ge 1 && $seconds -le 300 ]]
export PROBE_PAGE=webrtc-probe.html PROBE_SECONDS=$seconds PROBE_TIMEOUT=$((seconds+20))
bash /probe-wayland.sh "$1"
