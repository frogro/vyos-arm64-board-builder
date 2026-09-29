#!/bin/bash
# Host-side isolated codec probe: no live state/config/image replacement.
set -euo pipefail
IMAGE=${1:-localhost/vyarm-kiosk:hevc-candidate}
OUT=${2:?output log required}
PID=$(podman inspect kiosk-test --format '{{.State.Pid}}')
[[ "$PID" =~ ^[0-9]+$ && "$PID" -gt 1 ]]
WORK=$(mktemp -d /run/vyarm-hevc-probe.XXXXXX)
cleanup() { podman rm -f vyarm-hevc-probe >/dev/null 2>&1 || true; rm -rf "$WORK"; }
trap cleanup EXIT
cp -p "/proc/$PID/root/run/kiosk/Xauthority" "$WORK/Xauthority"
cat > "$WORK/probe.conf" <<'CONF'
sunshine_name = Isolated HEVC capability test
capture = x11
encoder = rkmpp
stream_audio = disabled
controller = disabled
keyboard = disabled
mouse = disabled
upnp = disabled
system_tray = disabled
port = 48989
bind_address = 127.0.0.1
CONF
set +e
timeout --signal=TERM 40s podman run --rm --name vyarm-hevc-probe --hostname kiosk-test \
 --network container:kiosk-test --ipc container:kiosk-test --device /dev/mpp_service --device /dev/dri/card0 \
 -v /sys/firmware/devicetree/base/compatible:/run/mpp/compatible:ro \
 -v "$WORK/Xauthority:/run/kiosk/Xauthority:ro" \
 -v "$WORK/probe.conf:/probe.conf:ro" --entrypoint /bin/sh "$IMAGE" \
 -c 'chgrp video /dev/mpp_service /dev/dri/card0 && chmod 660 /dev/mpp_service /dev/dri/card0 && runuser -u kiosk -- env DISPLAY=:0 XAUTHORITY=/run/kiosk/Xauthority xdpyinfo >/tmp/display-info 2>&1; if ! grep -q "dimensions:" /tmp/display-info; then cat /tmp/display-info; exit 2; fi; exec runuser -u kiosk -- env DISPLAY=:0 XAUTHORITY=/run/kiosk/Xauthority sunshine /probe.conf' > "$OUT" 2>&1
RC=$?
set -e
[[ "$RC" == 0 || "$RC" == 124 ]]
grep -F 'Found HEVC encoder: hevc_rkmpp' "$OUT"
grep -F 'Found H.264 encoder: h264_rkmpp' "$OUT"
