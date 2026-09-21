# Opt-in stateless MMAP capture-buffer experiment — 2026-09-21

Status: **live interposer experiment successful; Chromium source patch not yet built**.
Production kiosk, kernel, main branch and release workflows are unchanged.

## Controlled results

Same Chromium 153, sandbox enabled, isolated Weston 16 headless output, 1080p60
BT.709 limited testsrc2 material, same RK3588 kernel and V4L2 decoder.
Numbers are HTML `droppedVideoFrames`, **not network packet loss**.

| Input | Actual capture buffers | Dropped / total |
|---|---:|---:|
| H.264 B3/B-pyramid, 30 s | 6 | 257, 268, 284 / 1800 |
| Same | 8 | 6, 7, 8 / 1800 |
| Same | 12 | 6 / 1800 |
| H.264, 120 s (packet-copy loop) | 6 | 1122 / 7200 |
| Same | 8 | 69 / 7200 |
| H.265, 30 s | 8 | 7 / 1800 |
| Same | 10 | 3 / 1800 |

All reached end of stream with V4L2 hardware decoding. The seven short H.264
final-frame images were pixel-identical. This does not prove every intermediate
frame or fix the independent BT.709 Chromium import color issue. HEVC RPS/long-term
reference conformance remains a separate unresolved case.

Kernel trace with eight buffers: all 1800 capture QBUF/DQBUF events, no ring loss.
H.264 B-pyramid QBUF→DQBUF median 3.206 ms, submission-gap p95 18.285 ms;
previous six-buffer baseline p95 ~33.8 ms, similar ~3.2 ms QBUF→DQBUF.
Non-pyramid with eight: 7 HTML drops, submission-gap p95 18.131 ms.
CSV files retain timestamps, device queue event, buffer index and type. Reproduce
statistics with `../buffer-lifetime/summarize.py`. QBUF→DQBUF includes scheduling;
it is not a pure hardware performance counter. DQBUF→same-index-QBUF measures
buffer reuse/reference retention and naturally grows with a larger rotating pool.

Instrumented requestVideoFrameCallback runs had 261 vs 25 drops (six/eight),
processingDuration median 151.15 vs 153.5 ms and p95 236.6 vs 217.4 ms. This is
browser pipeline metadata, **not measured end-to-end KVM latency**. Extra JS affects
timing; do not merge these with the uninstrumented performance runs.

## Mechanism and reproducibility

`capture-count.c` is a disposable LD_PRELOAD ioctl adapter, compiled inside the
ARM64 GStreamer test image with `gcc -Wall -Wextra -Werror -O2 -fPIC -shared ... -ldl`.
It only changes positive MMAP CAPTURE allocations for the selected decoder device.
`VYARM_CAPTURE_EXTRA=2` adds two slots, bounded; `VYARM_CAPTURE_COUNT=8/12`
is the older absolute H.264-only mode. Logs record requested/overridden/returned
counts. Match ioctl using its low unsigned 32 bits because Chromium sign-extends
its int ioctl request. Initial `count-*` runs missed this and are **excluded**.
The earlier `hevc-count-*` comparison did not increase HEVC's eight buffers and
is also excluded; only `hevc-extra-*` proves 8→10.

Raw artifacts: ROCK `/config/kiosk-test/kernel-test3/capture-count/` and
`/config/kiosk-test/kernel-test3/buffer-lifetime-extra/`. `results.json` keeps reduced
browser metadata and allocation evidence, without embedded screenshots/large traces.

## Candidate generic integration

`0001-opt-in-extra-capture-buffers.patch` adds disabled-by-default Chromium feature
`V4L2ExtraCaptureBuffers`; field parameter `extra_buffers` defaults to 2, clamps
0..8 and respects VIDEO_MAX_FRAME. It applies only to stateless Request API + MMAP
capture allocation. No board-name checks; existing DMABUF/stateful/default paths
remain unchanged. A compiled browser and real display/latency/resolution-change
validation are still required. Do not install the interposer as production glue.

For F this targets local browser playback. For D it can help a browser receiver
using the same decoder path; it does not alter the KVM sender's hardware encoder.
Neither profile should gain a default encoder/codec switch from this experiment.

## Upstream context, not a ready-made fix

Chromium's 2022 change [178d40f](https://github.com/chromium/chromium/commit/178d40fd1ec8dba2de85abd05e0ffad48746d6ab)
discusses budgeting buffers for codec references and renderer retention. Its
[revert 60da61d](https://github.com/chromium/chromium/commit/60da61d75fff49f2741f5a86702215ac6e9f8b04)
explicitly cites CTS failures. Therefore the historical patch must not be blindly
backported. Current source already has renderer-pool budgeting elsewhere, while
the active V4L2 MMAP allocation is reference-count + 2. Our bounded opt-in isolates
that allocation as a test variable; a permanent change needs reset, allocation
failure, low-delay and resolution-change coverage across drivers.
