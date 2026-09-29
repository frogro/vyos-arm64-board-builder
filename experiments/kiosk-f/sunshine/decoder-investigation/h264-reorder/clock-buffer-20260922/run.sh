#!/bin/bash
set -euo pipefail
root=/config/kiosk-test/kernel-test3/clock-buffer-20260922
sample() {
 while :; do
  date -Ins
  grep -E 'clk_rkvdec0_core |clk_rkvdec0_ca |clk_rkvdec0_hevc_ca |aclk_rkvdec0 ' /sys/kernel/debug/clk/clk_summary
  sleep 0.5
 done
}
sample > "$root/clocks.txt" & sampler=$!
trap 'kill "$sampler" 2>/dev/null || true' EXIT
for pair in baseline1:0 extra1:2 extra2:2 baseline2:0; do
 name=${pair%:*}; extra=${pair#*:}
 echo "START $name $(date -Is)" | tee -a "$root/progress.txt"
 CAPTURE_EXTRA="$extra" PERF_RUNS=1 bash /config/kiosk-test/kernel-test3/capture-count/tools-v3-both/test-browser-performance.sh localhost/vyarm-kiosk:weston16-test3 /config/kiosk-test/kernel-test3/browser-perf-fixtures "$root/$name" /dev/video2 /dev/media0
 echo "DONE $name $(date -Is)" | tee -a "$root/progress.txt"
done
systemctl is-active vyos-container-kiosk-test.service vyos-kvm-video.service > "$root/restored.txt"
