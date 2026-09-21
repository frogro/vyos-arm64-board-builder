#!/bin/bash
set -euo pipefail
export XDG_RUNTIME_DIR=/tmp/wayland-runtime
export WAYLAND_DISPLAY=wayland-probe
mkdir -m 700 "$XDG_RUNTIME_DIR"
weston --backend=headless --renderer=gl --no-config --socket="$WAYLAND_DISPLAY" --width=1280 --height=720 --idle-time=0 --log=/tmp/weston.log &
weston_pid=$!
trap 'kill "$weston_pid" 2>/dev/null || true; cat /tmp/weston.log >&2' EXIT
for i in $(seq 1 50); do
 test ! -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" || break
 kill -0 "$weston_pid"
 sleep .1
done
test -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY"
python3 /probe.py "$1" wayland-native
