# Test3 1080p60 comparison, 2026-09-21

Kernel 6.18.50-vyos-f-test3; same unmodified Chromium153 and Weston/Mali test
image as browser-test3-results. Each fixture1800frames/30s, target8Mbps,
actual H2648.091Mbps / HEVC8.053Mbps. Non-root Chromium sandbox retained.
Independent runs in H264/HEVC,HEVC/H264,H264/HEVC order; production D/F unchanged.

Whole disposable browser/compositor/probe cgroup CPU median after5s warmup:
H26460.67% of one core, HEVC55.40%. Browser reported droppedFrames median
723/1800 H264,670/1800 HEVC; all six ended with V4L2VideoDecoder/platform=true.
These counters do NOT establish physical monitor frame loss; headless/compositor
pacing and browser integration remain under investigation. rVFC submissions are
not identical to droppedFrames accounting. Playback duration is not latency.
No performance promotion/default change follows from this result.

Reducing only headless output/CSS geometry to640x360 (same1080p60 bitstreams,
one run each) did not materially fix the counters:714 H264/668 HEVC drops.
Thus it is not sufficient merely to reduce the output pixel area.

Separate GStreamer explicit v4l2slh264dec/v4l2slh265dec + fakesink sync=false:
1800 output chain buffers and EOS each, three runs. ~211fps H264/~300fps HEVC.
Includes parser/decoder/sink and per-buffer logging. This establishes decoder
throughput for these fixtures, not browser/render/stream latency or all profiles.
First MP4 attempt failed because deliberately minimal image lacks qtdemux and
fpsdisplaysink; successful test uses lossless Annex-B extraction and fakesink.

Controlled no-video/media-device test (DRI retained): H264 completed through
FFmpegVideoDecoder/platform=false; HEVC rejected with NotSupportedError.
No universal HEVC software fallback can be promised for this installed browser.

Color caveat discovered with new fixtures: final frame1799 matches content but
hardware canvas readback differs from explicit FFmpeg BT709 RGB reference by
mean[12.95,1.60,5.65] H264/[12.96,1.60,5.66] HEVC. Software H264 readback mean
[1.76,1.12,1.56]. Media tracks correctly report BT709/limited. Investigate YUV
import/conversion separately; this is not evidence that the RGA CSC patch failed
(RGA converter is not this browser path). Earlier720p sample pass is not a
blanket color guarantee. Full PNG/verbose logs retained in /tmp/vyarm-browser-perf
and live /config/kiosk-test/kernel-test3 results; committed JSON omits base64PNG.

Additional diagnostic --disable-gpu-vsync + --disable-frame-rate-limit worsened
the headless path: H264 timed out50s with only3 callbacks; HEVC ended but reported
948droppedFrames. Not adopted. Backend source explains forcedREC601 import; see
../BROWSER-COLOR-IMPORT.md and explicit601 reference match below1 RGB value/channel.
