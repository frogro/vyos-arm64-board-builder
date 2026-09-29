#!/bin/bash
set -euo pipefail
r=/config/kiosk-test/av1-transition-20260922
[[ $(uname -r) == 6.18.50-vyos-f-test4-av1-iommu ]]
[[ ! -d /sys/module/hantro_vpu ]]
[[ $(cat /sys/class/watchdog/watchdog0/state) == inactive ]]
[[ -z $(grub-editenv /boot/grub/grubenv list | sed -n 's/^next_entry=//p') ]]
mkdir -p "$r"
[[ ! -e "$r/started" ]]
date --iso-8601=seconds > "$r/started"
cat /proc/sys/kernel/random/boot_id > "$r/boot-id"
step() { echo "$(date --iso-8601=seconds) $*" | tee -a "$r/steps"; echo "VYARM_TRANSITION $*" > /dev/kmsg; sync "$r/steps"; }
cleanup() {
 set +e
 step CLEANUP_BEGIN
 podman rm -f vyarm-nuc-chromium-test >/dev/null 2>&1
 if [[ -d /sys/module/hantro_vpu ]]; then
  step CLEANUP_UNLOAD_BEGIN
  timeout -k 3 15 modprobe -r hantro_vpu
 fi
 if [[ ! -d /sys/module/hantro_vpu ]]; then
  for n in fdb50000 fdba0000 fdba4000 fdba8000 fdbac000; do
   d=/sys/bus/platform/devices/$n.video-codec
   [[ ! -d $d ]] || printf '\n' > "$d/driver_override"
  done
  systemctl stop vyarm-transition-fallback.timer vyarm-transition-watchdog.service
  step CLEANUP_DONE
 else
  step CLEANUP_FAILED_GUARDS_REMAIN_ARMED
 fi
}
trap cleanup EXIT
cp /config/kiosk-test/av1-reset-candidates-20260922/watchdog.py /run/vyarm-transition-watchdog.py
systemd-run --unit=vyarm-transition-watchdog --property=TimeoutStopSec=10 /usr/bin/python3 /run/vyarm-transition-watchdog.py
sleep 2
[[ $(cat /sys/class/watchdog/watchdog0/state) == active ]]
systemd-run --unit=vyarm-transition-fallback --on-active=7m /bin/systemctl reboot
root=/config/kiosk-test/chromium-nuc-20260922
runner=/config/kiosk-test/av1-timeout-cli-20260922/run-cli-browser.sh
run() {
 local mode=$1 label=$2 reserve=disabled
 [[ $mode != auto ]] || reserve=enabled
 step "BEGIN_$label"
 KIOSK_VIDEO_DECODE=$mode KIOSK_VIDEO_AV1_BUFFERS=$reserve PROBE_BROWSER=/candidate-p010/chrome PROBE_TIMEOUT=45 bash "$runner" av1 "$root/av1-main10-fixtures" "$label" 0 "${video:-}" "${media:-}"
 step "END_$label"
}
video=;media=
run software transition-software-before
[[ ! -d /sys/module/hantro_vpu ]]
for n in fdb50000 fdba0000 fdba4000 fdba8000 fdbac000; do
 d=/sys/bus/platform/devices/$n.video-codec
 [[ ! -d $d ]] || echo vyarm-av1-test-block > "$d/driver_override"
done
step LOAD_BEGIN
modprobe v4l2_jpeg
insmod /config/kiosk-test/av1-timeout-cli-20260922/hantro-errors.ko vyarm_test_remove_reset_mask=3 vyarm_test_av1_remove_pulse=1
step LOAD_DONE
for p in /sys/devices/platform/fdc70000.video-codec/video4linux/video*; do [[ ! -d $p ]] || video=/dev/$(basename "$p"); done
for p in /sys/devices/platform/fdc70000.video-codec/media*; do [[ ! -d $p ]] || media=/dev/$(basename "$p"); done
[[ -c $video && -c $media ]]
run auto transition-hardware
for n in fdc70000.video-codec fdca0000.iommu; do
 echo "$n $(cat /sys/devices/platform/$n/power/runtime_status)" >> "$r/pm-after-hardware"
done
run software transition-software-loaded
step UNLOAD_BEGIN
modprobe -r hantro_vpu
step UNLOAD_DONE
video=;media=
run software transition-software-after-unload
step ALL_COMPLETED
