set -euo pipefail
[ "$(uname -r)" = 6.18.50-vyos-f-test3 ]
root=/config/kiosk-test/kernel-test3/hantro-reset-causal
cleanup() {
 /sbin/rmmod hantro_vpu 2>/dev/null || true
 /sbin/rmmod v4l2_jpeg 2>/dev/null || true
 for d in fdb50000 fdba0000 fdba4000 fdba8000 fdbac000; do
  p=/sys/bus/platform/devices/$d.video-codec
  [ ! -d "$p" ] || printf '\n' > "$p/driver_override"
 done
}
trap cleanup EXIT
for d in fdb50000 fdba0000 fdba4000 fdba8000 fdbac000; do
 p=/sys/bus/platform/devices/$d.video-codec
 [ ! -d "$p" ] || { [ ! -L "$p/driver" ]; [ "$(cat "$p/driver_override")" = '(null)' ]; }
done
for d in fdb50000 fdba0000 fdba4000 fdba8000 fdbac000; do
 p=/sys/bus/platform/devices/$d.video-codec
 [ ! -d "$p" ] || echo vyarm-av1-test-block > "$p/driver_override"
done
/sbin/insmod /config/kiosk-test/kernel-test3/hantro-av1-live/v4l2-jpeg.ko
/sbin/insmod "$root/hantro-vpu.ko" vyarm_test_keep_av1_reset_deasserted=1
video=; media=
for retry in $(seq 1 40); do
 for p in /sys/devices/platform/fdc70000.video-codec/video4linux/video*; do
  [ -d "$p" ] && video=/dev/$(basename "$p")
 done
 for p in /sys/devices/platform/fdc70000.video-codec/media*; do
  [ -d "$p" ] && media=/dev/$(basename "$p")
 done
 if [ -n "$video" ] && [ -n "$media" ] && [ -c "$video" ] && [ -c "$media" ]; then break; fi
 sleep .25
done
[ -c "$video" ]; [ -c "$media" ]
echo "DEVICES $video $media" >&2

mkdir -p "$root/decode"
for run in 1 2 3; do
 echo "HASH_RUN $run $(date -Is)"
 timeout -k 5 70 podman run --rm --name vyarm-av1-reset-hash --network none --memory 512m --device "$video" --device "$media" -v /config/kiosk-test/kernel-test3/hantro-av1-live:/fixtures:ro localhost/vyarm-kiosk:gst128-decoder-test-20260921 gst-launch-1.0 -q filesrc location=/fixtures/test.obu ! av1parse ! v4l2slav1dec ! video/x-raw,format=NV12 ! fdsink fd=1 | python3 /config/kiosk-test/kernel-test3/hantro-av1-live/hash-frames.py > "$root/decode/$run.json"
 echo "HASH_DONE $run"
done
echo "BROWSER_LONG_START $(date -Is)"
PERF_RUNS=3 bash "$root/tools/test-browser-performance.sh" localhost/vyarm-kiosk:weston16-test3 "$root/fixtures" "$root/browser-long" "$video" "$media"
echo "BROWSER_LONG_DONE $(date -Is)"
cat /sys/kernel/debug/pm_genpd/av1/current_state
sync
