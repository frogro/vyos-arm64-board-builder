#!/bin/bash
set -euo pipefail
for node in /dev/dri/renderD*; do
 gid=$(stat -c %g "$node")
 if ! getent group "$gid" >/dev/null; then groupadd -g "$gid" "renderhost$gid"; fi
 group=$(getent group "$gid" | cut -d: -f1)
 usermod -a -G "$group" kiosk
done
mkdir -p /tmp/physical-runtime
chown kiosk:kiosk /tmp/physical-runtime
chmod 700 /tmp/physical-runtime
seatd -u kiosk -g video > /tmp/seatd.log 2>&1 & seat=$!
trap 'kill "$seat" 2>/dev/null || true; cat /tmp/seatd.log >&2; cat /tmp/weston.log >&2' EXIT
for i in $(seq 1 30); do [ ! -S /run/seatd.sock ] || break; sleep .1; done
cat > /tmp/physical.ini <<'INI'
[core]
idle-time=0
[shell]
panel-position=none
locking=false
[output]
name=HDMI-A-1
mode=1920x1080@60
transform=rotate-90
INI
runuser -u kiosk -- env XDG_RUNTIME_DIR=/tmp/physical-runtime WAYLAND_DISPLAY=physical-wayland LIBSEAT_BACKEND=seatd SEATD_SOCK=/run/seatd.sock /usr/bin/weston --backend=drm --renderer=gl --drm-device=card0 --continue-without-input --config=/tmp/physical.ini --socket=physical-wayland --log=/tmp/weston.log & wp=$!
trap 'kill "$wp" "$seat" 2>/dev/null || true; cat /tmp/seatd.log >&2; cat /tmp/weston.log >&2' EXIT
for i in $(seq 1 100); do [ ! -S /tmp/physical-runtime/physical-wayland ] || break; kill -0 "$wp"; sleep .1; done
runuser -u kiosk -- env XDG_RUNTIME_DIR=/tmp/physical-runtime WAYLAND_DISPLAY=physical-wayland python3 /probe.py "$1" wayland-native
