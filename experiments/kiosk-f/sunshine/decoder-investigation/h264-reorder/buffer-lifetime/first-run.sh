#!/bin/bash
set -euo pipefail
root=/config/kiosk-test/kernel-test3/buffer-lifetime
trace=/sys/kernel/tracing/instances/vyarm-decoder-lifetime
mkdir "$trace"
trap 'echo 0 > "$trace/tracing_on"; echo 0 > "$trace/events/v4l2/enable"; rmdir "$trace"' EXIT
 echo 0 > "$trace/tracing_on"
echo mono > "$trace/trace_clock"
echo 4096 > "$trace/buffer_size_kb"
for event in v4l2_qbuf v4l2_dqbuf; do
 echo 'minor == 2' > "$trace/events/v4l2/$event/filter"
 echo 1 > "$trace/events/v4l2/$event/enable"
done
for variant in baseline no-pyramid; do
 fixtures=/config/kiosk-test/kernel-test3/browser-perf-fixtures
 [[ $variant != no-pyramid ]] || fixtures=/config/kiosk-test/kernel-test3/h264-reorder/b3-no-pyramid
 echo > "$trace/trace"
 echo 1 > "$trace/tracing_on"
 PERF_RUNS=1 bash "$root/tools/test-browser-performance.sh" localhost/vyarm-kiosk:weston16-test3 "$fixtures" "$root/$variant" /dev/video2 /dev/media0
 echo 0 > "$trace/tracing_on"
 cat "$trace/trace" > "$root/$variant.trace"
 cat "$trace"/per_cpu/cpu*/stats > "$root/$variant.stats"
done
