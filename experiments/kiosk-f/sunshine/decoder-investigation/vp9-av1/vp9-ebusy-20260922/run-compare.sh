set -euo pipefail
[ "$(uname -r)" = 6.18.50-vyos-f-test3 ]
root=/config/kiosk-test/kernel-test3/vp9-ebusy-compare
mkdir "$root"
stamp=$(date '+%Y-%m-%d %H:%M:%S')
cleanup() {
 if [ -d /sys/module/rockchip_vdec ]; then /sbin/rmmod rockchip_vdec || return 1; fi
 /sbin/modprobe rockchip_vdec
 journalctl -k --since "$stamp" --no-pager > "$root/kernel.txt"
}
trap cleanup EXIT
for variant in vp9-mail vp9-ebusy; do
 [ "$(cat /sys/module/rockchip_vdec/refcnt)" = 0 ]
 /sbin/rmmod rockchip_vdec
 /sbin/insmod "/tmp/rockchip-vdec-$variant.ko"
 sleep 1
 video=; media=
 for p in /sys/bus/platform/devices/fdc38100.video-codec/video4linux/video*; do video=/dev/$(basename "$p"); done
 for p in /sys/bus/platform/devices/fdc38100.video-codec/media*; do media=/dev/$(basename "$p"); done
 [ -c "$video" ]; [ -c "$media" ]
 echo "START $variant $(date -Is)"
 bash /tmp/test-stateless-decode.sh localhost/vyarm-kiosk:gst128-decoder-test-20260921 /config/kiosk-test/builds/gst128-decoder-20260921/vyarm-gst128-fixtures "$root/$variant-decode" "$video" "$media"
 timeout -k 5 70 podman run --rm --network none --memory 512m --device "$video" --device "$media" -v /config/kiosk-test/kernel-test3/vp9-mail-test:/fixtures:ro localhost/vyarm-kiosk:gst128-decoder-test-20260921 /fixtures/vp9-ivf-probe /fixtures/test-vp9.ivf | python3 /config/kiosk-test/kernel-test3/hantro-av1-live/hash-frames.py > "$root/$variant-vp9-hashes.json"
 cmp /config/kiosk-test/kernel-test3/vp9-mail-test/reference-hashes.json "$root/$variant-vp9-hashes.json"
 echo "DECODE PASS $variant"
 PERF_RUNS=1 bash /config/kiosk-test/kernel-test3/browser-perf-tools/test-browser-performance.sh localhost/vyarm-kiosk:weston16-test3 /config/kiosk-test/kernel-test3/browser-perf-fixtures "$root/$variant-browser" "$video" "$media"
 PERF_RUNS=1 bash /config/kiosk-test/kernel-test3/vp9-mail-test/tools/test-browser-performance.sh localhost/vyarm-kiosk:weston16-test3 /config/kiosk-test/kernel-test3/vp9-mail-test/long-fixtures "$root/$variant-browser-vp9" "$video" "$media"
 echo "DONE $variant $(date -Is)"
done
