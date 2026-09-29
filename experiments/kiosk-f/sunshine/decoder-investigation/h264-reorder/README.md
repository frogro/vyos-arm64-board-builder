# H264 reordering / reference-frame isolation

2026-09-21. Disposable Weston 16 runtime, Chromium 153, test3 kernel.
No production settings changed. This follows weston-stable-compare.

Three independently encoded synthetic testsrc2 1080p60 30-second videos:
- b1: bframes=1, other fast-preset defaults.
- b3-no-pyramid: bframes=3, b-pyramid=none.
- b3-ref1: bframes=3, ref=1, default B pyramid.

Same target/max/VBV 8M and keyint60; structural changes also affect encoder
choices, so these are not identical-quality bitstreams. Encode metadata and
actual x264 option lines are retained. ffprobe refs alone is not a reliable
measure of all DPB requirements. HEVC unchanged as paired control.

Use make-fixtures.sh NEW_DIRECTORY PATH_TO_BROWSER_PROBE_HTML, add the same
HEVC control fixture to each subdirectory, then the existing
../test-browser-performance.sh with PERF_RUNS=1 and the Weston16 test image.

Separate verbose decoder runs are diagnostic only: their presentation/CPU
numbers must not be mixed with uninstrumented performance comparisons.


SPS inspection with FFmpeg trace_headers confirms:

| Fixture | max_num_ref_frames | max_num_reorder_frames | max_dec_frame_buffering |
|---|---:|---:|---:|
| Baseline B3 pyramid | 4 | 2 | 4 |
| B1 | 2 | 1 | 2 |
| B3 no pyramid | 2 | 1 | 2 |
| B3 ref=1, pyramid | 4 | 2 | 4 |

Thus the nominal ref=1 encoder experiment does NOT independently reduce
advertised DPB size when the B pyramid remains enabled. Treat these as
correlated structural characteristics, not proof of an individual field
causing drops. A further instrumented decoder/renderer investigation is
needed before changing driver or Chromium buffer allocation.

Local Chromium153 source review: V4L2StatelessVideoDecoderBackend retains
V4L2 buffers while references remain, queues output requests in display
order, and waits for the front request to become ready. The pipeline
normally estimates 16 renderer buffers for non-low-latency playback.
ReduceHardwareVideoDecoderBuffers is disabled by default in reviewed
source; merely assuming that switch is responsible would be unsupported.


## Initial results

All six uninstrumented runs ended with 1800 total frames, 1920x1080, and
V4L2VideoDecoder/platform=true. HTML presentation drops:

| H264 fixture | H264 drops | Paired HEVC drops | H264 CPU, % of one core |
|---|---:|---:|---:|
| B1 | 5 | 15 | 56.53 |
| B3 no pyramid | 8 | 9 | 58.94 |
| B3 ref=1 with pyramid | 278 | 5 | 65.40 |

Prior baseline B3 pyramid:267 drops on the same stable16 runtime. B-frames
alone are therefore insufficient to explain the performance difference.
The pyramid/reorder-depth/reference-lifetime combination is the stronger
lead. Fixture encoder changes are correlated, so no exact root-cause claim.

## Diagnostic allocation evidence

Both baseline and no-B verbose runs request 17 V4L2 OUTPUT buffers (coded
input) and 6 CAPTURE buffers (decoded output), using V4L2_MEMORY_MMAP.
This actual path uses driver-allocated buffers, num_codec_reference_frames
+2 in V4L2VideoDecoder::ContinueChangeResolution; the general renderer-pool
estimate of16 is not its CAPTURE allocation. Buffer occupancy/lifetime,
not simply the requested count, remains to be instrumented. Existing
release logs do not prove starvation or queue stalls. Do not change kernel
or buffer count based only on this correlation.


## Reversed-order repeat and completion

Second no-pyramid H264:10 drops (HEVC8), then original baseline:258
(HEVC3). Both again1800 total frames and hardware decoder confirmed.
Together with earlier267 baseline and8 no-pyramid, this reproduces the
association in reversed order. No production change or proposed default
change. All transient test services completed; only kiosk-test running,
production D/F services active. No physical-screen result asserted.

Verbose diagnostics used the same harness, overriding the performance
mode's removal of vmodule with:
`--vmodule=*v4l2_video_decoder*=3,*platform_video_frame_pool*=3,*video_decoder_pipeline*=2`
Exact browser flags and media events are retained in diagnostic JSON;
allocation excerpts retained separately. Decoder allocation != occupancy.

Next engineering experiment: instrument CAPTURE buffer occupancy and frame
release/display-order readiness, then compare an isolated build with a
larger decoded-output pool if evidence supports it. Do not backport an
unproven kernel change or claim universal H264 conformance from these clips.
