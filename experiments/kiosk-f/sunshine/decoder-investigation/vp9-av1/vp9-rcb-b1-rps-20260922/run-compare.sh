set -euo pipefail
[ "$(uname -r)" = 6.18.50-vyos-f-test3 ]
root=/config/kiosk-test/kernel-test3/vp9-rcb-b1-rps-compare3
mkdir "$root"
stamp=$(date '+%Y-%m-%d %H:%M:%S')
was_kvm=$(systemctl is-active vyos-kvm-video.service || true)
cleanup() {
 /sbin/rmmod rockchip_vdec 2>/dev/null || true
 for m in synopsys_hdmirx rockchip_rga v4l2_mem2mem videobuf2_v4l2 videodev v4l2_h264; do
  if [ -d /sys/module/$m ]; then /sbin/rmmod "$m" || return 1; fi
 done
 /sbin/modprobe videodev
 /sbin/modprobe rockchip_rga
 /sbin/modprobe synopsys_hdmirx
 /sbin/modprobe rockchip_vdec
 [ "$was_kvm" != active ] || systemctl start vyos-kvm-video.service
 journalctl -k --since "$stamp" --no-pager > "$root/kernel.txt"
}
trap cleanup EXIT
systemctl stop vyos-kvm-video.service
for m in rockchip_vdec synopsys_hdmirx rockchip_rga v4l2_mem2mem videobuf2_v4l2 videodev v4l2_h264; do
 [ ! -d /sys/module/$m ] || /sbin/rmmod "$m"
done
/sbin/insmod /tmp/videodev-rps.ko
/sbin/insmod /tmp/v4l2-h264-b1.ko
/sbin/modprobe rockchip_rga
/sbin/modprobe synopsys_hdmirx
/sbin/modprobe v4l2_mem2mem
/sbin/insmod /tmp/rockchip-vdec-rcb-b1.ko
for variant in combined; do
 [ "$(cat /sys/module/rockchip_vdec/refcnt)" = 0 ]
 sleep 1
 video=; media=
 for p in /sys/bus/platform/devices/fdc38100.video-codec/video4linux/video*; do video=/dev/$(basename "$p"); done
 for p in /sys/bus/platform/devices/fdc38100.video-codec/media*; do media=/dev/$(basename "$p"); done
 [ -c "$video" ]; [ -c "$media" ]
 /tmp/rps-try-probe "$video" | tee "$root/rps-boundary.txt"
 echo "START $variant $(date -Is)"
 bash /tmp/test-stateless-decode.sh localhost/vyarm-kiosk:gst128-decoder-test-20260921 /config/kiosk-test/builds/gst128-decoder-20260921/vyarm-gst128-fixtures "$root/$variant-decode" "$video" "$media"
 timeout -k 5 70 podman run --rm --network none --memory 512m --device "$video" --device "$media" -v /config/kiosk-test/kernel-test3/vp9-mail-test:/fixtures:ro localhost/vyarm-kiosk:gst128-decoder-test-20260921 /fixtures/vp9-ivf-probe /fixtures/test-vp9.ivf | python3 /config/kiosk-test/kernel-test3/hantro-av1-live/hash-frames.py > "$root/$variant-vp9-hashes.json"
 cmp /config/kiosk-test/kernel-test3/vp9-mail-test/reference-hashes.json "$root/$variant-vp9-hashes.json"
 echo "DECODE PASS $variant"
 PERF_RUNS=1 bash /config/kiosk-test/kernel-test3/browser-perf-tools/test-browser-performance.sh localhost/vyarm-kiosk:weston16-test3 /config/kiosk-test/kernel-test3/browser-perf-fixtures "$root/$variant-browser" "$video" "$media"
 PERF_RUNS=1 bash /config/kiosk-test/kernel-test3/vp9-mail-test/tools/test-browser-performance.sh localhost/vyarm-kiosk:weston16-test3 /config/kiosk-test/kernel-test3/vp9-mail-test/long-fixtures "$root/$variant-browser-vp9" "$video" "$media"
 PERF_RUNS=1 bash /config/kiosk-test/kernel-test3/browser-perf-tools/test-browser-performance.sh localhost/vyarm-kiosk:weston16-test3 /config/kiosk-test/kernel-test3/h264-no-bframes "$root/$variant-browser-no-b" "$video" "$media"
 echo "DONE $variant $(date -Is)"
done
