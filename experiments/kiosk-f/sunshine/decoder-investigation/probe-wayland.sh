#!/bin/bash
set -euo pipefail
export XDG_RUNTIME_DIR=/tmp/wayland-runtime
export WAYLAND_DISPLAY=wayland-probe
mkdir -m 700 "$XDG_RUNTIME_DIR"
config_args=(--no-config)
if [[ -n ${PROBE_REPAINT_WINDOW:-} ]]; then
 [[ $PROBE_REPAINT_WINDOW =~ ^[0-9]+$ && $PROBE_REPAINT_WINDOW -le 100 ]]
 printf '[core]\nrepaint-window=%s\n' "$PROBE_REPAINT_WINDOW" > /tmp/weston-probe.ini
 config_args=(--config=/tmp/weston-probe.ini)
fi
refresh=${PROBE_REFRESH:-60000}
[[ $refresh =~ ^[0-9]+$ && $refresh -ge 1000 && $refresh -le 240000 ]]
weston --refresh-rate="$refresh" --backend=headless --renderer=gl "${config_args[@]}" --socket="$WAYLAND_DISPLAY" --width="${PROBE_WIDTH:-1280}" --height="${PROBE_HEIGHT:-720}" --idle-time=0 --log=/tmp/weston.log &
weston_pid=$!
trap 'kill "$weston_pid" 2>/dev/null || true; cat /tmp/weston.log >&2' EXIT
for i in $(seq 1 50); do
 test ! -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" || break
 kill -0 "$weston_pid"
 sleep .1
done
test -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY"
python3 /probe.py "$1" wayland-native
