set -euo pipefail
[ "$(uname -r)" = 6.18.50-vyos-f-test3 ]
root=/config/kiosk-test/kernel-test3/vp9-mail-test
[ -s "$root/reference-hashes.json" ]
[ "$(cat /sys/module/rockchip_vdec/refcnt)" = 0 ]
! fuser /dev/video2 /dev/media0 >/dev/null 2>&1
stamp=$(date '+%Y-%m-%d %H:%M:%S')
cleanup() {
 podman rm -f vyarm-vp9-mail-probe >/dev/null 2>&1 || true
 if [ -d /sys/module/rockchip_vdec ]; then
  /sbin/rmmod rockchip_vdec || { echo "Decoder still busy; cannot restore baseline" >&2; return 1; }
 fi
 /sbin/modprobe rockchip_vdec
 journalctl -k --since "$stamp" --no-pager > "$root/kernel.txt"
}
trap cleanup EXIT
/sbin/rmmod rockchip_vdec
/sbin/insmod /tmp/rockchip-vdec-vp9-mail.ko
video=;media=
for i in $(seq 1 20); do
 for p in /sys/bus/platform/devices/fdc38100.video-codec/video4linux/video*; do [ ! -d "$p" ] || video=/dev/$(basename "$p"); done
 for p in /sys/bus/platform/devices/fdc38100.video-codec/media*; do [ ! -d "$p" ] || media=/dev/$(basename "$p"); done
 [ -n "$video" ] && [ -c "$video" ] && [ -n "$media" ] && [ -c "$media" ] && break
 sleep .25
done
[ -c "$video" ]; [ -c "$media" ]
v4l2-ctl -d "$video" --list-formats-out | tee "$root/formats.txt"
grep -q VP9F "$root/formats.txt"
PERF_RUNS=1 bash "$root/tools/test-browser-performance.sh" localhost/vyarm-kiosk:weston16-test3 "$root/long-fixtures" "$root/browser-long" "$video" "$media"
