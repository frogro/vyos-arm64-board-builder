#!/bin/bash
set -euo pipefail
r=/config/kiosk-test/av1-transition-20260922
[[ $(uname -r) == 6.18.50-vyos-f-test4-av1-iommu ]]
[[ ! -d /sys/module/hantro_vpu ]]
[[ $(cat /sys/class/watchdog/watchdog0/state) == inactive ]]
[[ ! -e $r/flags-started ]]
date --iso-8601=seconds > "$r/flags-started"
step() { echo "$(date --iso-8601=seconds) $*" | tee -a "$r/flags-steps"; echo "VYARM_FLAGS $*" > /dev/kmsg; sync "$r/flags-steps"; }
cleanup() { set +e; podman rm -f vyarm-nuc-chromium-test >/dev/null 2>&1; systemctl stop vyarm-flags-fallback.timer vyarm-flags-watchdog.service; step CLEANUP_DONE; }
trap cleanup EXIT
cp /config/kiosk-test/av1-reset-candidates-20260922/watchdog.py /run/vyarm-flags-watchdog.py
systemd-run --unit=vyarm-flags-watchdog --property=TimeoutStopSec=10 /usr/bin/python3 /run/vyarm-flags-watchdog.py
sleep 2
[[ $(cat /sys/class/watchdog/watchdog0/state) == active ]]
systemd-run --unit=vyarm-flags-fallback --on-active=5m /bin/systemctl reboot
root=/config/kiosk-test/chromium-nuc-20260922
step LEGACY_FLAGS_BEGIN
PROBE_BROWSER=/candidate-p010/chrome PROBE_SOFTWARE=1 ACCURATE_YUV_MATRIX=1 EXTRA_AV1_CAPTURE=1 PROBE_TIMEOUT=45 bash "$root/run-p010.sh" av1 "$root/av1-main10-fixtures" transition-legacy-flags 1
step LEGACY_FLAGS_DONE
[[ ! -d /sys/module/hantro_vpu ]]
step CLI_FLAGS_BEGIN
KIOSK_VIDEO_DECODE=software KIOSK_VIDEO_AV1_BUFFERS=disabled PROBE_BROWSER=/candidate-p010/chrome PROBE_TIMEOUT=45 bash /config/kiosk-test/av1-timeout-cli-20260922/run-cli-browser.sh av1 "$root/av1-main10-fixtures" transition-cli-flags-repeat 0
step CLI_FLAGS_DONE
[[ ! -d /sys/module/hantro_vpu ]]
