#!/bin/bash
set -euo pipefail
/tmp/mediamtx /fixtures/mediamtx.yml > /tmp/mediamtx.log 2>&1 &
mtx=$!
trap 'kill "$mtx" 2>/dev/null || true; cat /tmp/mediamtx.log >&2' EXIT
export PROBE_PAGE=webrtc-probe.html PROBE_TIMEOUT=40
bash /probe-wayland.sh "$1"
