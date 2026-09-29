#!/bin/bash
# Separate D GStreamer/RGA trial. Requires matching signed experimental module.
set -euo pipefail
[[ $EUID == 0 ]] || exit 2
MODULE=${1:?candidate module}; DEVICE=${2:?HDMI capture device}; OUT=${3:?new absolute output directory}
[[ -f "$MODULE" && -c "$DEVICE" && "$OUT" == /* && ! -e "$OUT" ]] || exit 2
[[ $(basename "$DEVICE") =~ ^video[0-9]+$ ]] || exit 2
[[ $(cat "/sys/class/video4linux/$(basename "$DEVICE")/name") == stream_hdmirx ]] || exit 2
for plugin in v4l2convert mpph264enc h264parse; do gst-inspect-1.0 "$plugin" >/dev/null; done
WAS_ACTIVE=0
if systemctl is-active --quiet vyos-kvm-video.service; then WAS_ACTIVE=1; fi
UNIT="vyarm-kvm-rga-capture-rollback-$$"
umask 077; mkdir "$OUT"
cat > "$OUT/rollback.sh" <<EOF
#!/bin/bash
set -e
modprobe -r rockchip_rga
modprobe rockchip_rga
if [[ '$WAS_ACTIVE' == 1 ]]; then systemctl start vyos-kvm-video.service; fi
EOF
chmod 700 "$OUT/rollback.sh"
cleanup() { "$OUT/rollback.sh"; systemctl stop "$UNIT.timer" >/dev/null 2>&1 || true; }
trap cleanup EXIT
systemd-run --unit="$UNIT" --on-active=75s "$OUT/rollback.sh"
if [[ $WAS_ACTIVE == 1 ]]; then systemctl stop vyos-kvm-video.service; fi
rmmod rockchip_rga
insmod "$MODULE"
v4l2-ctl -d "$DEVICE" --set-dv-bt-timings query > "$OUT/timing.log"
timeout --signal=TERM --kill-after=5s 45s gst-launch-1.0 -e \
 v4l2src "device=$DEVICE" num-buffers=120 \
 '!' video/x-raw,format=BGR,width=1920,height=1080,framerate=60/1 \
 '!' v4l2convert '!' video/x-raw,format=NV12,colorimetry=bt709 \
 '!' mpph264enc bps=8000000 gop=60 '!' h264parse \
 '!' filesink "location=$OUT/capture.h264" > "$OUT/encode.log" 2>&1
"$OUT/rollback.sh"
ffprobe -v error -count_frames -select_streams v:0 \
 -show_entries stream=codec_name,width,height,nb_read_frames,color_range,color_space,color_primaries,color_transfer \
 -of json "$OUT/capture.h264" > "$OUT/stream.json"
python3 - "$OUT/stream.json" <<'PY'
import json,sys,os
s=json.load(open(sys.argv[1]))['streams'][0]
assert (s['codec_name'],s['width'],s['height'],int(s['nb_read_frames']))==('h264',1920,1080,120),s
if os.environ.get('VYARM_MPP_COLORIMETRY')=='1':
    assert s.get('color_range')=='tv' and s.get('color_space')=='bt709',s
    assert s.get('color_primaries')=='bt709' and s.get('color_transfer')=='bt709',s
print(json.dumps(s))
PY
