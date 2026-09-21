# Buffer-path and B-pyramid research, 2026-09-21

Authorization extended to 19:30 Europe/Berlin (17:30 UTC). Research searched
web, GitHub issues and Chromium commit history, plus Armbian/Raspberry Pi
forum results. No exact, verified fix for our H264 B-pyramid presentation
loss was found in this search; this is not proof that none exists.

## Why our path uses six buffers

Chromium153 VideoDecoderPipeline::PickDecoderOutputFormat, Linux branch:
no custom allocator + directly renderable candidate (NV12 in live log) ->
reset main_frame_pool and let V4L2 allocate. V4L2VideoDecoder subsequently
requests MMAP CAPTURE buffers = codec-reference count +2. Actual log:6.
The alternative externally allocated frame-pool branch budgets reference
frames +1 + estimated renderer depth (normally16 non-low-latency). These
are different paths in upstream Chromium, not a custom six-buffer patch
introduced by our kiosk. Six is for this stream, not a universal limit.
MMAP is the allocation/API mode, not evidence of software decoding or a
mandatory CPU copy; export/import to graphics is a separate step.

Sources:
https://chromium.googlesource.com/chromium/src/+/HEAD/media/gpu/chromeos/video_decoder_pipeline.cc
https://chromium.googlesource.com/chromium/src/+/refs/heads/main/media/gpu/v4l2/v4l2_video_decoder.cc

## Patch triage

- 760e144 (2023): defer buffer requeue until surface and displayed frame
  both release it. Important reference-lifetime rationale, but files under
  media/gpu/v4l2/stateless/ belong to V4L2StatelessVideoDecoder, distinct from
  our logged V4L2VideoDecoder + V4L2StatelessVideoDecoderBackend. Not a direct
  cherry-pick for the observed active backend.
- b420223 (2023): clear surface references after dequeue, same other backend.
- f0755cd (2024): allocate using decoder reference count, same other backend.
- 0e161fe (2024): increase coded INPUT buffers from1 to4 in other decoder.
  Our active backend already requests17 OUTPUT/input buffers. Not a match.
- 9573035 (2022): increase stateful-backend buffers. Our decoder is stateless.
Full commit messages, dates and file paths in upstream-buffer-commits.json.

Additional projects reviewed:
https://gist.github.com/amazingfate/c9b5d558d1f0f4f756348b7e4c43be3c
https://github.com/dongioia/rock5bplus-rkvdec2
https://github.com/Polycom-Open-Firmware/chromium-a53
https://github.com/saiarcot895/chromium-ubuntu-build/issues/65
https://git.ti.com/cgit/arago-project/meta-arago/commit/meta-arago-distro?id=30a611f56a4bd74d421e36ecddf705b956c01648
These cover enabling codecs/platforms, other backends, initialization and
rendering fixes; none established an exact B-pyramid fix for our stack.

Forum leads:
https://forum.armbian.com/topic/30458-hardware-video-acceleration-not-working-in-chromium/
(search/embed content available, direct fetch502), RKMPP enablement issue;
https://forum.armbian.com/topic/32449-repository-for-v4l2request-hardware-video-decoding-rockchip-allwinner/page/4/
https://forums.raspberrypi.com/viewtopic.php?t=288732
Pi encoder lacking B-frames is not evidence of decoder inability here.
No arbitrary no-sandbox flags or unrelated driver patches adopted.

## Next measurement

Use existing Chromium media/gpu trace counter "V4L2 queue sizes" on original
B-pyramid and no-pyramid fixtures. Counts show buffers queued at device,
not all retained references/free buffers, so do not interpret zero queued
as proof of starvation. Trace metrics are instrumented diagnostic runs.


## Completed trace comparison

All four runs ended with1800 frames and V4L2 hardware confirmed. H264
baseline272 presentation drops, no-pyramid8. At the trace points, CAPTURE
queue counts are mostly0 or1 in both. Gaps from a zero-queue counter to the
next counter (excluding >=1 second startup/end outliers), p95:35.020ms
baseline versus18.537ms no-pyramid. These are irregular trace-event gaps,
not measured buffer-starvation durations or pure decoder service times.
No proof of full/empty free pool can be drawn from these counters alone.

Trace harness is trace-browser-device-probe.py. Place it as
browser-device-probe.py beside a copy of the existing performance launcher
and probe-wayland.sh, then run that launcher against the two fixture sets.
Tracing uses media,gpu, ReturnAsStream, a64MB collection limit and retains
only V4L2 queue counters in result JSON. These runs are diagnostic and
must not be merged into uninstrumented CPU performance statistics.
Services completed, D/F active, only production kiosk-test remains.
