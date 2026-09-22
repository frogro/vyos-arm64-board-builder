#!/bin/bash
set -euo pipefail
r=/config/kiosk-test/av1-reset-candidates-20260922/identity-domain
mkdir -p "$r"
[[ ! -e $r/events.txt ]]
exec > >(tee "$r/events.txt") 2>&1
grep -q 'vyarm_av1_candidates=1' /proc/cmdline
[[ ! -d /sys/module/hantro_vpu ]]
p=/sys/module/vsi_iommu/parameters
echo Y > "$p/vyarm_identity_guard"
echo N > "$p/vyarm_nonsleeping_tlb"
d=/sys/devices/platform/fdc70000.video-codec
[[ ! -L $d/driver ]]
g=$(readlink -f "$d/iommu_group")
[[ $(ls "$g/devices") == fdc70000.video-codec ]]
[[ $(cat "$g/type") == DMA ]]
power=/sys/devices/platform/fdca0000.iommu/power
old=$(cat "$power/control")
cleanup() {
 set +e
 echo Y > "$p/vyarm_identity_guard"
 echo DMA > "$g/type"
 echo "$old" > "$power/control"
 if [[ $(cat "$g/type") == DMA ]]; then
  systemctl stop vyarm-av1-domain-fallback.timer vyarm-av1-domain-watchdog.service
 fi
}
trap cleanup EXIT
systemd-run --unit=vyarm-av1-domain-watchdog --property=TimeoutStopSec=10 /usr/bin/python3 /run/vyarm-av1-watchdog.py
sleep 2
[[ $(cat /sys/class/watchdog/watchdog0/state) == active ]]
systemd-run --unit=vyarm-av1-domain-fallback --on-active=6m /bin/systemctl reboot
for i in 1 2 3; do
 echo "IDENTITY_ATTACH_$i"
 echo identity > "$g/type"
 cat "$g/type"
 echo auto > "$power/control"
 sleep 2
 [[ $(cat "$power/runtime_status") == suspended ]]
 echo "IDENTITY_RESUME_$i"
 echo on > "$power/control"
 [[ $(cat "$power/runtime_status") == active ]]
 echo auto > "$power/control"
 sleep 2
 echo "DMA_RESTORE_$i"
 echo DMA > "$g/type"
 [[ $(cat "$g/type") == DMA ]]
 sleep 2
 echo "CYCLE_${i}_PASS"
done
echo IDENTITY_DOMAIN_TEST_OK
