#!/bin/bash
set -euo pipefail
r=/config/kiosk-test/av1-timeout-cli-20260922/browser-cli-combined
mkdir -p "$r"
[[ ! -e $r/trace.txt ]]
[[ $(cat /sys/module/vsi_iommu/parameters/vyarm_identity_guard) == Y ]]
[[ $(cat /sys/module/vsi_iommu/parameters/vyarm_nonsleeping_tlb) == Y ]]
bash /config/kiosk-test/kernel-test4/preflight.sh
[[ -z $(grub-editenv /boot/grub/grubenv list | sed -n 's/^next_entry=//p') ]]
t=/sys/kernel/tracing/instances/vyarm-av1-cli-noevents
[[ ! -d $t ]]
mkdir "$t"
cleanup() {
 set +e
 podman rm -f vyarm-av1-cli-noevents-trace >/dev/null 2>&1
 if [[ -d /sys/module/hantro_vpu ]]; then
  [[ $(cat /sys/module/hantro_vpu/parameters/vyarm_test_av1_remove_pulse) == Y ]] && modprobe -r hantro_vpu
 fi
 for n in fdb50000 fdba0000 fdba4000 fdba8000 fdbac000; do
  d=/sys/bus/platform/devices/$n.video-codec
  [[ ! -d $d ]] || printf '\n' > "$d/driver_override"
 done
 echo 0 > "$t/tracing_on"
 cat "$t/trace" > "$r/trace.txt"
 echo 0 > "$t/events/enable"
 rmdir "$t"
 if [[ ! -d /sys/module/hantro_vpu ]]; then
  systemctl stop vyarm-av1-cli-noevents-fallback.timer vyarm-av1-cli-noevents-watchdog.service
 fi
}
trap cleanup EXIT
systemd-run --unit=vyarm-av1-cli-noevents-watchdog --property=TimeoutStopSec=10 /usr/bin/python3 /run/vyarm-av1-watchdog.py
sleep 2
[[ $(cat /sys/class/watchdog/watchdog0/state) == active ]]
systemd-run --unit=vyarm-av1-cli-noevents-fallback --on-active=8m /bin/systemctl reboot
for e in rpm_suspend rpm_resume rpm_return_int rpm_idle; do
 [[ ! -d $t/events/rpm/$e ]] || {
 echo 'name == "fdc70000.video-codec" || name == "fdca0000.iommu"' > "$t/events/rpm/$e/filter"
 echo 1 > "$t/events/rpm/$e/enable"
 }
done
for e in device_pm_callback_start device_pm_callback_end; do
 echo 'device == "fdc70000.video-codec" || device == "fdca0000.iommu"' > "$t/events/power/$e/filter"
 echo 1 > "$t/events/power/$e/enable"
done
echo 0 > "$t/events/enable"
echo 1 > "$t/tracing_on"
for n in fdb50000 fdba0000 fdba4000 fdba8000 fdbac000; do
 d=/sys/bus/platform/devices/$n.video-codec
 [[ ! -d $d ]] || echo vyarm-av1-test-block > "$d/driver_override"
done
echo LOAD_BEGIN > "$t/trace_marker"
modprobe v4l2_jpeg
insmod /config/kiosk-test/av1-timeout-cli-20260922/hantro-errors.ko vyarm_test_remove_reset_mask=3 vyarm_test_av1_remove_pulse=1
sleep 2
echo DECODE_BEGIN > "$t/trace_marker"
video=;media=
for p in /sys/devices/platform/fdc70000.video-codec/video4linux/video*; do [[ ! -d $p ]] || video=/dev/$(basename "$p"); done
for p in /sys/devices/platform/fdc70000.video-codec/media*; do [[ ! -d $p ]] || media=/dev/$(basename "$p"); done
[[ -c $video && -c $media ]]
root=/config/kiosk-test/chromium-nuc-20260922
# Real browser P010 decode, then forced client termination on a separate stream.
for mode in auto software; do
 reserve=disabled
 [[ $mode != auto ]] || reserve=enabled
 KIOSK_VIDEO_DECODE=$mode KIOSK_VIDEO_AV1_BUFFERS=$reserve PROBE_BROWSER=/candidate-p010/chrome PROBE_TIMEOUT=45 bash /config/kiosk-test/av1-timeout-cli-20260922/run-cli-browser.sh av1 "$root/av1-main10-fixtures" "media-cli-combined-$mode" 0 "$video" "$media"
done
KIOSK_VIDEO_DECODE=auto KIOSK_VIDEO_AV1_BUFFERS=enabled PROBE_BROWSER=/candidate-p010/chrome PROBE_TIMEOUT=45 bash /config/kiosk-test/av1-timeout-cli-20260922/run-cli-browser.sh av1 "$root/av1-main10-fixtures" media-cli-combined-no-decoder 0
echo DECODE_DONE > "$t/trace_marker"
sleep 3
for n in fdc70000.video-codec fdca0000.iommu; do
 echo "$n $(cat /sys/devices/platform/$n/power/runtime_status)" >> "$r/pm-state.txt"
done
echo REMOVE_BEGIN > "$t/trace_marker"
modprobe -r hantro_vpu
echo REMOVE_DONE > "$t/trace_marker"
sleep 5
echo IDLE_DONE > "$t/trace_marker"
echo TRACE_DECODE_REMOVE_OK
