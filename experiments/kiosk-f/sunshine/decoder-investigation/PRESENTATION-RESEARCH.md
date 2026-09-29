# Browser presentation investigation, 2026-09-21

Question: do 1080p60 HTML dropped-frame counters imply a missing kernel driver?
Current evidence does not establish that. Test3 decodes all1800 frames through
V4L2 at~211fps H264/~300fps HEVC without presentation. Five-minute WHEP tests
decode~60fps,0 packet loss/freezes,18/0 RTP drops. HTML presentation counters
remain high and differ from requestVideoFrameCallback counts. Physical display
smoothness remains untested.

## Source review

- Chromium VideoNG describes separate decoding and compositor presentation:
  https://developer.chrome.com/docs/chromium/videong
- Weston14 headless backend has a software finish-frame timer, defaults60000mHz,
  schedules it after repaint with millisecond resolution. Unlike DRM scanout
  this is a virtual display; headless results cannot directly establish HDMI
  frame loss. Hypothesis: timing/presentation feedback contributes; not proven.
  https://github.com/wayland-mirror/weston/blob/14.0/libweston/backend-headless/headless.c
- RK3588 maintainer report documents stock Chromium150 plus V4L2, Wayland and
  optional zero-copy flags. Its historical VP9/ANGLE fixes and AV1 IOMMU work
  are codec-specific, not demonstrated fixes for our H264/HEVC presentation.
  https://github.com/dongioia/rock5bplus-rkvdec2#browser-video--stock-chromium-150
- Armbian first-hand mainline report similarly distinguishes V4L2 from vendor
  MPP. Our hybrid test kernel must be checked directly; generic forum statements
  that mainline never exposes mpp_service do not describe all downstream kernels.
  https://forum.armbian.com/topic/61497-guide-system-wide-in-browser-hw-video-decode-on-rk3588-mainline-debian-13-trixie-%E2%80%94-and-the-4k30-cma-gotcha-nobody-warns-you-about/
- COSMIC issue2677 shows presentation feedback can fail independently of decode.
  Different compositor/GPU and fullscreen symptom: analogy only, not our fix.
  https://github.com/pop-os/cosmic-comp/issues/2677

## Isolated comparison

Same1080p60 files and browser153; three variants: explicit60Hz baseline,
AcceleratedVideoDecodeLinuxZeroCopyGL+enable-zero-copy+gpu-rasterization,
and virtual120Hz output. Last variant changes ONLY the disposable virtual
output timing, not stream frame rate, production output or physical monitor.
Sandbox remains active. Never promote flags based solely on process exit.

Color correctness is a separate confirmed mismatch: see BROWSER-COLOR-IMPORT.md.
SPS/RPS reference samples also require pixel/order investigation; see
rps-conformance-test3. Neither is yet a proven cause of high presentation
counters in ordinary synthetic clips.

First two repeated pairs (drops/1800; all ended on V4L2):

| Virtual output | H264 | HEVC |
|---|---:|---:|
|60Hz baseline|711 /702|675 /678|
|60Hz zero-copy flags (one run)|694|676|
|120Hz virtual output|44 /66|19 /19|

This strongly implicates presentation timing of the virtual output, not lack
of raw decoding capacity. No physical120Hz requirement is inferred. Next
comparison retains60Hz and uses Weston core repaint-window=16 instead of
the default7ms. Headless repaint schedules finish timer after rendering;
compositor.c schedules next repaint at stamp+period-repaint_window.

Completed60Hz repaint-window comparisons:
-16ms: H264371/377 drops, HEVC135/130 (two runs each).
-20ms: H264380, HEVC139 (one run each).
All1800frames ended with V4L2 hardware decoder selected. Timing tuning helps
but is not a complete60Hz presentation fix. No production flag change.

Reproduce with test-browser-performance.sh and explicit PERF_RUNS,
PERF_REFRESH (mHz,1000..240000), PERF_REPAINT_WINDOW (ms,0..100),
PERF_ZERO_COPY=1. Defaults retain60Hz and Weston's default repaint window.
Latest generalized helper was validated live with20ms; shader/renderer and
codec selection remain in JSON evidence. Network-none, sandbox enabled.

Next decisive work: trace presentation feedback/frame cadence or compare
a newer Weston in isolation; later verify actual DRM/HDMI scanout with user.
Do not infer hardware display drops solely from the headless counters.
