# Decoder clock and capture-pool comparison, 2026-09-22

ROCK 5B, 6.18.50-vyos-f-test3 original installed decoder modules. Sandboxed
Chromium153, isolated Weston16, same 1080p60/30s fixtures and existing v3
capture-allocation interposer. Two repetitions in ABBA order: baseline,
extra2, extra2, baseline. No governor, voltage, kernel module or production
configuration changes. This is not a test of the compiled Chromium patch.

## Clock finding

Live /sys/class/devfreq exposes only fb000000.gpu, governor simple_ondemand
(the only available governor). There is no NPU or video decoder devfreq node.
The suggested fdab0000.npu or *vpu* governor commands therefore cannot set
the decoder frequency on this kernel. NPU is not the video decoder.

The Test3 rkvdec driver obtains/enables clocks and gates them with runtime PM;
it has no devfreq integration or clk_set_rate calls. rk3588-base.dtsi assigns
core/CABAC 600MHz, HEVC CABAC 1000MHz, AXI 800MHz. Actual framework-reported
rates are sampled from debugfs clk_summary every 0.5 seconds during all runs:
core/CABAC 594MHz, HEVC CABAC 1000MHz, AXI 786431998Hz.

See results.json for all observed values and sample count. These are clock
framework rates, not independent hardware frequency measurements; sampling
cannot exclude subinterval transitions or other bottlenecks. No evidence here
for decoder devfreq downclocking as the source of H264 presentation drops.
No claim that these clocks are the maximum electrically possible/supported.

## Interpretation

The buffer adapter targets V4L2 MMAP CAPTURE allocations, not FFmpeg MPP
extra_hw_frames. H264 uses 6 vs 8 capture slots; HEVC uses 8 vs 10. Verify
actual allocations in results.json allocation_logs. Counts are HTML dropped
video frames, not network packet loss. All runs should be checked for ended,
1800 total frames and V4L2VideoDecoder/platform=true before accepting results.

The comparison isolates the previously identified Chromium capture-pool
budget issue with constant observed decoder rates. It does not establish
physical display latency, broad codec conformance, or a benefit for D's
low-delay receiver. No change to D/F defaults follows from these tests.
Raw clock log and full browser artifacts remain at
/config/kiosk-test/kernel-test3/clock-buffer-20260922 on the ROCK.

## Observed results

| Order | Extra slots | H264 drops /1800 | HEVC drops /1800 |
|---|---:|---:|---:|
| baseline1 |0|256|4|
| extra1 |2|9|4|
| extra2 |2|6|7|
| baseline2 |0|270|11|

All eight runs ended and reported V4L2VideoDecoder/platform=true. All four
clock rates remained identical across 578 samples. Baseline regression after
removing extra slots supports the capture-budget explanation; no comparable
HEVC improvement is demonstrated. Both D video and F kiosk services remained
active at completion. Compiled Chromium patch, physical latency and broad
conformance testing remain outstanding.
