#!/bin/bash
# Disposable diagnostic only. Does not change the running kiosk browser.
set -euo pipefail
IMAGE=${1:?image required}
PAGE=${2:?absolute path to webgl-probe.html required}
OUT=${3:?output log required}
HOST_CONTAINER=${4:-kiosk-test}
shopt -s nullglob
NODES=(/dev/dri/renderD*)
[[ ${#NODES[@]} == 1 ]] || { echo 'Specify/test GPU selection separately: expected one render node' >&2; exit 2; }
NODE=${NODES[0]}
PID=$(podman inspect "$HOST_CONTAINER" --format '{{.State.Pid}}')
[[ "$PID" =~ ^[0-9]+$ && "$PID" -gt 1 ]]
HOSTNAME=$(podman exec "$HOST_CONTAINER" hostname)
WORK=$(mktemp -d /run/vyarm-chromium-probe.XXXXXX)
NAME=vyarm-chromium-gpu-probe
cleanup() { podman rm -f "$NAME" >/dev/null 2>&1 || true; rm -rf "$WORK"; }
trap cleanup EXIT
cp -p "/proc/$PID/root/run/kiosk/Xauthority" "$WORK/Xauthority"
# Shared network namespace supplies the abstract X11 socket; no debug port.
# no-sandbox is confined to this disposable diagnostic, never kiosk defaults.
timeout --signal=TERM 45s podman run --rm --name "$NAME" --hostname "$HOSTNAME" \
 --network "container:$HOST_CONTAINER" --ipc "container:$HOST_CONTAINER" \
 --user kiosk --group-add "$(stat -c %g "$NODE")" --device "$NODE" \
 -e DISPLAY=:0 -e XAUTHORITY=/run/kiosk/Xauthority \
 -v "$WORK/Xauthority:/run/kiosk/Xauthority:ro" -v "$PAGE:/probe.html:ro" \
 --entrypoint chromium "$IMAGE" \
 --headless --no-sandbox --disable-dev-shm-usage --no-first-run \
 --disable-background-networking --user-data-dir=/tmp/chromium-probe \
 --enable-gpu --use-gl=angle --use-angle=gles --ignore-gpu-blocklist \
 --dump-dom file:///probe.html > "$OUT" 2>&1
python3 - "$OUT" <<'PY'
import html,json,re,sys
text=open(sys.argv[1]).read()
m=re.search(r'<pre id="result">(.*?)</pre>',text,re.S)
if not m: raise SystemExit('No browser probe result')
r=json.loads(html.unescape(m.group(1)))
print(json.dumps(r))
if 'error' in r or r.get('pixel') != [255,0,0,255]: raise SystemExit(1)
renderer=r.get('renderer','').lower()
if not renderer or any(x in renderer for x in ('swiftshader','llvmpipe','softpipe')): raise SystemExit(1)
PY
