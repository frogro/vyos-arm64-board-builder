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
0..8 and respects VIDEO_MAX_FRAME. It applies only to non-low-delay stateless Request API + MMAP
capture allocation. The source candidate now retains the original allocation
when Initialize receives low_delay=true; this guard still needs compiled validation. No board-name checks; existing DMABUF/stateful/default paths
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

## Why this path differs from the general Chromium pool

In matching Debian Chromium 153 source,
`media/gpu/chromeos/video_decoder_pipeline.cc:1187` selects the Linux V4L2
directly renderable format, resets `main_frame_pool_`, and returns early.
The subsequent common allocation budget (`num_codec_reference_frames + 1 +
estimated_num_buffers_for_renderer_`) is consequently not used on this path.
`V4L2VideoDecoder::ContinueChangeResolution` then uses MMAP with references + 2.
This source-level difference is consistent with the controlled allocation tests.
It is not a claim that all Chromium platforms or all V4L2 drivers share the issue.

Before any default promotion: compile and test the actual patch, define behavior
when a driver returns fewer buffers or allocation fails, cover changing coded
resolution within one stream, and measure physical display/end-to-end latency.
The current source candidate fails allocation as before if its requested extra
slots cannot be supplied; it does not yet implement an automatic smaller-pool
retry. Keeping the feature disabled by default preserves the established path.

## Follow-up and scope restriction

- One extra slot (6→7) H.264: 7/9/8 drops in three 1800-frame runs;
  long 7200-frame run 68 drops. Paired long 6→8 run: 60 drops.
- Eight accurately checked seeks/pause/resumes passed for both codecs,
  baseline and +2. H.264 HTML drops 74→9, HEVC 8→12. The first server lacked
  HTTP Range support and silently restarted near zero; those `seek-extra-*`
  trials are invalid seek evidence. `seek-range-*` verifies presented mediaTime
  within 250 ms of each target and supports HTTP 206/Accept-Ranges.
- Five source reloads 1080→720→1080→720→1080 passed for both codecs with/without
  +2; dimensions and advancing playback checked. This is source replacement,
  **not an in-band coded-resolution change within one stream**.
- Higher-reference H.264 fixture: x264 ref=8,bframes=3,b-pyramid=normal,10 s,
  1080p60/8M. SPS max_num_ref_frames=8,max_dec_frame_buffering=8,reorder=2.
  Chromium actually requests15 capture slots here. Baseline/+1/+2 return
  15/16/17 and drop2/4/1 of600 frames. Thus extra slots are not beneficial
  for every input; the problem is the smaller allocation on the original input.
- Repeated fresh instances pass. One +2 startup run has24 H264 drops while
  test fixture preparation caused concurrent I/O; do not equate all repetitions
  with perfectly idle-host benchmark conditions.

### D receiver comparison: do not enable globally

Real isolated MediaMTX WebRTC, Weston16, no-B source, 60 seconds per codec,
then reverse-order repeat. All connect/end and all report zero packet loss.
HTML drops (baseline vs +2): H264145/416 and120/217; HEVC242/241 and273/348.
RTP decoder counters are distinct and mostly low (H26418/1 then0/4;
HEVC1/0 then0/0). Some runs report a freeze. No physical end-to-end latency
measurement and no demonstrated D benefit. Initial nominal60 runs accidentally
omitted the seconds URL argument and only ran20; they are excluded here.

The candidate feature therefore explicitly skips low-delay sessions. Do not
change D defaults, general browser flags, or all codecs globally based on F's
file-playback improvement. Keep H264 compatibility fallback. The live adapter
forced extra slots regardless of low-delay mode to expose this distinction;
it does not validate the source guard or represent a production implementation.
