#!/bin/bash
set -euo pipefail
r=/config/kiosk-test/av1-reset-candidates-20260922/tlb
mkdir -p "$r"
[[ ! -e $r/trace.txt ]]
grep -q 'vyarm_av1_candidates=1' /proc/cmdline
bash /config/kiosk-test/kernel-test4/preflight.sh
cp /config/kiosk-test/av1-reset-candidates-20260922/watchdog.py /run/vyarm-av1-watchdog.py
p=/sys/module/vsi_iommu/parameters
printf '%s\n' N > "$p/vyarm_identity_guard"
printf '%s\n' Y > "$p/vyarm_nonsleeping_tlb"
cat "$p"/vyarm_*
[[ -z $(grub-editenv /boot/grub/grubenv list | sed -n 's/^next_entry=//p') ]]
t=/sys/kernel/tracing/instances/vyarm-av1-candidate-tlb
[[ ! -d $t ]]
mkdir "$t"
cleanup() {
 set +e
 podman rm -f vyarm-av1-candidate-tlb-trace >/dev/null 2>&1
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
  systemctl stop vyarm-av1-candidate-tlb-fallback.timer vyarm-av1-candidate-tlb-watchdog.service
 fi
}
trap cleanup EXIT
systemd-run --unit=vyarm-av1-candidate-tlb-watchdog --property=TimeoutStopSec=10 /usr/bin/python3 /run/vyarm-av1-watchdog.py
sleep 2
[[ $(cat /sys/class/watchdog/watchdog0/state) == active ]]
systemd-run --unit=vyarm-av1-candidate-tlb-fallback --on-active=8m /bin/systemctl reboot
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
echo 1 > "$t/tracing_on"
for n in fdb50000 fdba0000 fdba4000 fdba8000 fdbac000; do
 d=/sys/bus/platform/devices/$n.video-codec
 [[ ! -d $d ]] || echo vyarm-av1-test-block > "$d/driver_override"
done
for cycle in 1 2 3; do
echo "CYCLE_${cycle}_LOAD_BEGIN" > "$t/trace_marker"
modprobe v4l2_jpeg
insmod /config/kiosk-test/av1-reset-research-20260922/hantro-pulse.ko vyarm_test_remove_reset_mask=3 vyarm_test_av1_remove_pulse=1
sleep 2
echo DECODE_BEGIN > "$t/trace_marker"
video=;media=
for p in /sys/devices/platform/fdc70000.video-codec/video4linux/video*; do [[ ! -d $p ]] || video=/dev/$(basename "$p"); done
for p in /sys/devices/platform/fdc70000.video-codec/media*; do [[ ! -d $p ]] || media=/dev/$(basename "$p"); done
[[ -c $video && -c $media ]]
fixtures=/config/kiosk-test/kernel-test3/hantro-av1-live
timeout -k 5 60 podman run --rm --name vyarm-av1-candidate-tlb-trace --network none --memory 512m --device "$video" --device "$media" -v "$fixtures:/fixtures:ro" localhost/vyarm-kiosk:gst128-decoder-test-20260921 gst-launch-1.0 -q filesrc location=/fixtures/test.obu ! av1parse ! v4l2slav1dec ! video/x-raw,format=NV12 ! fdsink fd=1 2>"$r/decode-$cycle.log" | python3 "$fixtures/hash-frames.py" > "$r/hardware-$cycle.json"
cmp "$fixtures/software.json" "$r/hardware-$cycle.json"
echo DECODE_DONE > "$t/trace_marker"
sleep 3
for n in fdc70000.video-codec fdca0000.iommu; do
 echo "$n $(cat /sys/devices/platform/$n/power/runtime_status)" >> "$r/pm-state.txt"
done
echo REMOVE_BEGIN > "$t/trace_marker"
modprobe -r hantro_vpu
echo REMOVE_DONE > "$t/trace_marker"
sleep 5
echo "CYCLE_${cycle}_IDLE_DONE" > "$t/trace_marker"
echo "CYCLE_${cycle}_PASS"
done
echo TRACE_DECODE_REMOVE_OK
