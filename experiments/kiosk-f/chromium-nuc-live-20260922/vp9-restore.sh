#!/bin/bash
set -euo pipefail
r=/config/kiosk-test/chromium-nuc-20260922/vp9-modules
podman rm -f vyarm-nuc-chromium-test >/dev/null 2>&1 || true
systemctl stop vyos-kvm-video.service
for m in rockchip_vdec synopsys_hdmirx rockchip_rga v4l2_mem2mem videobuf2_v4l2 videodev v4l2_h264; do
 [[ ! -d /sys/module/$m ]] || rmmod "$m"
done
modprobe videodev
modprobe rockchip_rga
modprobe synopsys_hdmirx
modprobe rockchip_vdec
[[ $(cat "$r/kvm-before") != active ]] || systemctl start vyos-kvm-video.service
printf 'RESTORED %s\n' "$(date -Is)" > "$r/restored.txt"
