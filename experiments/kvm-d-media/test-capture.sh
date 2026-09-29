#!/bin/bash
# Explicit, bounded profile-D alternative. Does not install or replace anything.
# Usage: sudo ./test-capture.sh IMAGE /dev/videoN h264-mpp-fixed|hevc-mpp-fixed OUTPUT_DIR
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run as root on the test host' >&2; exit 2; }
IMAGE=${1:?image required}; DEVICE=${2:?capture device required}
MODE=${3:?mode required}; OUT=${4:?new absolute output directory required}
case "$MODE" in
 h264-mpp-fixed) ENCODER=h264_rkmpp; MUX=h264 ;;
 hevc-mpp-fixed) ENCODER=hevc_rkmpp; MUX=hevc ;;
 *) echo 'Unsupported test mode' >&2; exit 2 ;;
esac
[[ "$OUT" == /* && ! -e "$OUT" && -c "$DEVICE" && -c /dev/mpp_service ]] || exit 2
[[ $(basename "$DEVICE") =~ ^video[0-9]+$ ]] || exit 2
# This first test harness supports the existing D HDMI-RX BGR24 path only.
[[ $(cat "/sys/class/video4linux/$(basename "$DEVICE")/name") == stream_hdmirx ]] || exit 2
podman image exists "$IMAGE"
# Check candidate capability before interrupting the existing stream.
podman run --rm --network=none "$IMAGE" -hide_banner -encoders 2>&1 | grep -q "$ENCODER"
UNIT="vyarm-kvm-media-rollback-$$"
CONTAINER="vyarm-kvm-media-probe-$$"
WAS_ACTIVE=0
if systemctl is-active --quiet vyos-kvm-video.service; then WAS_ACTIVE=1; fi
umask 077
mkdir "$OUT"
cat > "$OUT/rollback.sh" <<EOF
#!/bin/bash
podman rm -f '$CONTAINER' >/dev/null 2>&1 || true
if [[ '$WAS_ACTIVE' == 1 ]]; then systemctl start vyos-kvm-video.service; fi
EOF
chmod 700 "$OUT/rollback.sh"
cleanup() {
 "$OUT/rollback.sh"
 systemctl stop "$UNIT.timer" >/dev/null 2>&1 || true
}
trap cleanup EXIT
systemd-run --unit="$UNIT" --on-active=75s "$OUT/rollback.sh"
if [[ $WAS_ACTIVE == 1 ]]; then systemctl stop vyos-kvm-video.service; fi
v4l2-ctl -d "$DEVICE" --set-dv-bt-timings query > "$OUT/timing.log"
timeout --signal=TERM --kill-after=5s 45s podman run --rm --name "$CONTAINER" \
 --network=none --memory=512m --device "$DEVICE" --device /dev/mpp_service \
 --device /dev/dri/card0 \
 -v /sys/firmware/devicetree/base/compatible:/run/mpp/compatible:ro \
 -v "$OUT:/out:rw" "$IMAGE" -hide_banner -nostdin -loglevel info \
 -f v4l2 -capture_buffers 4 -input_format bgr24 -video_size 1920x1080 \
 -framerate 60 -i "$DEVICE" -an -frames:v 120 \
 -vf 'scale=out_color_matrix=bt709:out_range=tv,format=nv12' \
 -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 \
 -c:v "$ENCODER" -b:v 8000k -g 60 -f "$MUX" "/out/capture.$MUX" > "$OUT/encode.log" 2>&1
# Explicit restore before slower offline verification. EXIT cleanup remains armed.
"$OUT/rollback.sh"
ffprobe -v error -count_frames -select_streams v:0 \
 -show_entries stream=codec_name,width,height,nb_read_frames,color_range,color_space \
 -of json "$OUT/capture.$MUX" > "$OUT/stream.json"
python3 - "$OUT/stream.json" "$MUX" <<'PY'
import json,sys
s=json.load(open(sys.argv[1]))['streams'][0]
assert s['codec_name']==sys.argv[2], s
assert (s['width'],s['height'],int(s['nb_read_frames']))==(1920,1080,120),s
assert s['color_range']=='tv' and s['color_space']=='bt709',s
print(json.dumps(s))
PY
