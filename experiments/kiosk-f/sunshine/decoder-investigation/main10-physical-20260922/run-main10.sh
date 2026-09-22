set -euo pipefail
[ "$(uname -r)" = 6.18.50-vyos-f-test3 ]
root=/config/kiosk-test/kernel-test3/main10-combined-20260922
mkdir -p "$root"
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
 systemctl is-active vyos-container-kiosk-test.service vyos-kvm-video.service > "$root/restored.txt"
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

mkdir -p "$root/vp9-packed" "$root/hevc-packed"
set +e
set -o pipefail
timeout -k 5 90 podman run --rm --network none --memory 512m --device /dev/video2 --device /dev/media0 -v "$root:/work:ro" localhost/vyarm-kiosk:gst128-decoder-test-20260921 /work/vp9-main10-probe /work/test-vp9.ivf 2> "$root/vp9.log" | python3 /config/kiosk-test/kernel-test3/capture-count/main10-collect.py "$root/vp9-packed"
echo "VP9_PIPELINE_STATUS=$?" >> "$root/status.txt"
timeout -k 5 90 podman run --rm --network none --memory 512m --device /dev/video2 --device /dev/media0 -v /config/kiosk-test/kernel-test3/capture-count/main10-fixtures:/fixtures:ro localhost/vyarm-kiosk:gst128-decoder-test-20260921 gst-launch-1.0 -q filesrc location=/fixtures/test.hevc ! h265parse ! v4l2slh265dec ! fdsink fd=1 2> "$root/hevc.log" | python3 /config/kiosk-test/kernel-test3/capture-count/main10-collect.py "$root/hevc-packed"
echo "HEVC_PIPELINE_STATUS=$?" >> "$root/status.txt"
set -e
