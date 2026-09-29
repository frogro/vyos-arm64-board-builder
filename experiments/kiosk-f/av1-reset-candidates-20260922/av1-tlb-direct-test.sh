#!/bin/bash
set -euo pipefail
r=/config/kiosk-test/av1-reset-candidates-20260922/tlb-direct
mkdir -p "$r"
[[ ! -e $r/events.txt ]]
exec > >(tee "$r/events.txt") 2>&1
grep -q 'vyarm_av1_candidates=1' /proc/cmdline
[[ ! -d /sys/module/hantro_vpu ]]
p=/sys/module/vsi_iommu/parameters
echo N > "$p/vyarm_identity_guard"
echo Y > "$p/vyarm_nonsleeping_tlb"
d=/sys/devices/platform/fdc70000.video-codec
[[ ! -L $d/driver ]]
g=$(readlink -f "$d/iommu_group")
[[ $(cat "$g/type") == DMA ]]
power=/sys/devices/platform/fdca0000.iommu/power
old=$(cat "$power/control")
cleanup() {
 set +e
 [[ ! -d /sys/module/vyarm_av1_flush ]] || rmmod vyarm_av1_flush
 echo "$old" > "$power/control"
 if [[ ! -d /sys/module/vyarm_av1_flush ]]; then
  systemctl stop vyarm-av1-tlb-direct-fallback.timer vyarm-av1-tlb-direct-watchdog.service
 fi
}
trap cleanup EXIT
systemd-run --unit=vyarm-av1-tlb-direct-watchdog --property=TimeoutStopSec=10 /usr/bin/python3 /run/vyarm-av1-watchdog.py
sleep 2
[[ $(cat /sys/class/watchdog/watchdog0/state) == active ]]
systemd-run --unit=vyarm-av1-tlb-direct-fallback --on-active=6m /bin/systemctl reboot
for i in 1 2 3; do
 echo auto > "$power/control"
 sleep 2
 [[ $(cat "$power/runtime_status") == suspended ]]
 echo "SUSPENDED_FLUSH_$i"
 insmod /config/kiosk-test/av1-reset-candidates-20260922/vyarm_av1_flush.ko
 rmmod vyarm_av1_flush
 [[ $(cat "$power/runtime_status") == suspended ]]
 echo "ACTIVE_FLUSH_$i"
 echo on > "$power/control"
 [[ $(cat "$power/runtime_status") == active ]]
 insmod /config/kiosk-test/av1-reset-candidates-20260922/vyarm_av1_flush.ko
 rmmod vyarm_av1_flush
 echo "CYCLE_${i}_PASS"
done
echo TLB_DIRECT_TEST_OK
