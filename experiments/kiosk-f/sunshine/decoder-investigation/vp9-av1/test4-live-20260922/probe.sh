#!/bin/bash
# Run only on isolated test4; no production decoder defaults are changed.
set -euo pipefail
[[ $(uname -r) == 6.18.50-vyos-f-test4-av1-iommu ]]
r=/config/kiosk-test/kernel-test4
fixtures=/config/kiosk-test/kernel-test3/hantro-av1-live
[[ ! -d /sys/module/hantro_vpu ]]
cleanup() {
 podman rm -f vyarm-test4-av1-probe >/dev/null 2>&1 || true
 modprobe -r hantro_vpu 2>/dev/null || true
 for n in fdb50000 fdba0000 fdba4000 fdba8000 fdbac000; do
  d=/sys/bus/platform/devices/$n.video-codec
  [[ ! -d $d ]] || printf '\n' > "$d/driver_override"
 done
}
for n in fdb50000 fdba0000 fdba4000 fdba8000 fdbac000; do
 d=/sys/bus/platform/devices/$n.video-codec
 [[ ! -d $d ]] || { [[ ! -L $d/driver ]]; [[ $(cat "$d/driver_override") == '(null)' ]]; }
done
trap cleanup EXIT
for n in fdb50000 fdba0000 fdba4000 fdba8000 fdbac000; do
 d=/sys/bus/platform/devices/$n.video-codec
 [[ ! -d $d ]] || echo vyarm-av1-test-block > "$d/driver_override"
done
start=$(date --iso-8601=seconds)
for i in 1 2 3; do
 modprobe hantro_vpu vyarm_test_remove_reset_mask=3
 video=; media=
 for retry in $(seq 1 40); do
  for p in /sys/devices/platform/fdc70000.video-codec/video4linux/video*; do
   [[ ! -d $p ]] || video=/dev/$(basename "$p")
  done
  for p in /sys/devices/platform/fdc70000.video-codec/media*; do
   [[ ! -d $p ]] || media=/dev/$(basename "$p")
  done
  [[ -c $video && -c $media ]] && break
  sleep .25
 done
 [[ -c $video && -c $media ]]
 echo "Cycle $i: $video $media"
 timeout -k 5 75 podman run --rm --name vyarm-test4-av1-probe --network none --memory 512m \
  --device "$video" --device "$media" -v "$fixtures:/fixtures:ro" \
  localhost/vyarm-kiosk:gst128-decoder-test-20260921 \
  gst-launch-1.0 -q filesrc location=/fixtures/test.obu ! av1parse ! v4l2slav1dec ! \
  video/x-raw,format=NV12 ! fdsink fd=1 2>"$r/decode-$i.log" | \
  python3 "$fixtures/hash-frames.py" > "$r/hardware-$i.json"
 python3 - "$fixtures/software.json" "$r/hardware-$i.json" <<'PY'
import json,sys
reference=json.load(open(sys.argv[1])); actual=json.load(open(sys.argv[2]))
assert len(actual)==300, len(actual)
assert reference==actual, 'decoded frames differ'
print(f'{len(actual)} frames bit-exact against software reference')
PY
 modprobe -r hantro_vpu
 sleep 3
 journalctl -k --since "$start" --no-pager > "$r/kernel-during-tests.log"
 if grep -Eq 'failed to get ack|SError|BUG:|Oops:|iommu.*[Ff]ault' "$r/kernel-during-tests.log"; then
  echo 'Kernel error: stop further cycles'; exit 5
 fi
done
echo TEST4_AV1_THREE_CYCLES_OK
