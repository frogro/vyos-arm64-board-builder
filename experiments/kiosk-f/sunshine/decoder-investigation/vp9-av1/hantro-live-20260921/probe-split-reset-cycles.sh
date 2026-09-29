set -euo pipefail
[ "$(uname -r)" = 6.18.50-vyos-f-test3 ]
module=${1:-/tmp/hantro-split-reset-test.ko}
option=${2:-0}
cycles=${3:-3}
cleanup() {
 /sbin/rmmod hantro_vpu 2>/dev/null || true
 /sbin/rmmod v4l2_jpeg 2>/dev/null || true
 for n in fdb50000 fdba0000 fdba4000 fdba8000 fdbac000; do printf '\n' > /sys/bus/platform/devices/$n.video-codec/driver_override; done
}
for n in fdb50000 fdba0000 fdba4000 fdba8000 fdbac000; do
 d=/sys/bus/platform/devices/$n.video-codec
 [ ! -L "$d/driver" ]; [ "$(cat "$d/driver_override")" = '(null)' ]
done
[ ! -d /sys/module/hantro_vpu ]
trap cleanup EXIT
for n in fdb50000 fdba0000 fdba4000 fdba8000 fdbac000; do echo vyarm-av1-test-block > /sys/bus/platform/devices/$n.video-codec/driver_override; done
/sbin/insmod /config/kiosk-test/kernel-test3/hantro-av1-live/v4l2-jpeg.ko
for i in $(seq 1 "$cycles"); do
 stamp=$(date '+%Y-%m-%d %H:%M:%S')
 echo "CYCLE $i option=$option START $stamp"
 /sbin/insmod "$module" vyarm_test_remove_reset_mask="$option"
 ready=no
 for j in $(seq 1 20); do
  for p in /sys/devices/platform/fdc70000.video-codec/video4linux/video*; do
   if [ -e "$p" ] && [ -c "/dev/$(basename "$p")" ]; then ready=yes; fi
  done
  [ "$ready" = yes ] && break
  sleep .25
 done
 echo "READY $ready"
 [ "$ready" = yes ] || { journalctl -k --since "$stamp" --no-pager; exit 4; }
 sleep 1
 /sbin/rmmod hantro_vpu
 sleep 1
 log=$(journalctl -k --since "$stamp" --no-pager)
 printf '%s\n' "$log"
 if printf '%s\n' "$log" | grep -Eq 'failed to get ack|SError|BUG:|Oops:'; then exit 5; fi
 echo "CYCLE $i PASS"
done
