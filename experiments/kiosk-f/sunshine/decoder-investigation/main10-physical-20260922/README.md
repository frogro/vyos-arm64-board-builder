# Native10-bit and physical HDMI verification, 2026-09-22

## Physical output

ROCK5B HDMI-A-1 connected to RTK FHD HDR touchmonitor,1920x1080 mode with
90degree compositor rotation. Isolated Weston14.0.2 DRM/GL, Chromium153,
normal sandbox, Mali-G610/Panfrost renderer. Weston16 experiment was built
headless-only; these measurements are not same-compositor A/B benchmarks.
Temporary privileged diagnostic container, no production privilege change.

| Fixture 1080p60,30s | Capture slots | Dropped /1800 | Decoder |
|---|---:|---:|---|
| H264 B-pyramid |6→8|1|V4L2 hardware|
| HEVC8-bit |8|1|V4L2 hardware|
| VP9 Profile0 |10|5|V4L2 hardware|

User independently confirmed each of the three runs: visible and fluid.
Qualitative observation is not calibrated colorimetry, HDR validation or
end-to-end latency measurement. No general zero-drop/conformance claim.
H264/HEVC used original installed Test3 modules; VP9 used combined VP9/RCB/B1/
HEVC-validation modules from ../vp9-av1/vp9-rcb-b1-rps-20260922.
The capture adapter remains a disposable experiment, not compiled Chromium.

Initial seatd launch used unsupported -s and failed safely. Corrected to default
/run/seatd.sock. First running compositor/browser lacked renderD128 group:
llvmpipe and FFmpeg software fallback despite0 HTML drops; user saw no graphic.
This run is excluded. Adding node-derived supplementary group inside isolated
container and explicitly Page.bringToFront gave the verified physical results.
Kiosk stops only during each display trial and restarts via EXIT cleanup;
combined-module trial also restores original modules and D service afterwards.
The test keeps its final frame25s so user can observe. No kiosk URL/config edits.

## Native10-bit decoded data

Combined modules used for both codecs. Explicit GStreamer1.28.7 V4L2 stateless
decoders, native NV12_10LE40/NV15 output, no videoconvert rounding in comparison.

- VP9 Profile2,1920x1080,60fps,120frames,10-bit4:2:0 SDR BT709 limited:
  all120 native frame SHA256 match independently software-decoded/repacked input.
- HEVC Main10 existing fixture,1920x1080,60fps,300frames:
  all300 native hashes match the prior software-validated native reference in
  ../hevc-main10/hardware-frame-hashes.json.

VP9 generation: FFmpeg lavfi testsrc2=size=1920x1080:rate=60,format=yuv420p10le;
libvpx-vp9 profile2,120frames,8M,deadline=realtime,cpu-used6,threads2,row-mt1;
BT709 primaries/transfer/matrix,tv range; IVF output. Decode reference with
FFmpeg yuv420p10le then ../hevc-main10/pack-nv15.c and SHA256 per3888000 bytes.
Fixture/reference on development drive under tmp/vp9-main10-20260922 and ROCK
/config/kiosk-test/kernel-test3/main10-combined-20260922.
vp9-main10-probe.c adapts existing appsrc IVF probe only at output caps.

This is native decode proof, NOT10-bit Chromium playback or physical10-bit
scanout. Current browser lacks NV15 format support; NUC candidate still building.
No H264 High10 hardware claim; no12-bit, HDR or portrait stride conformance claim.
Native decoder hashes and physical8-bit playback are separate tests.

## Integration

See DEPENDENCIES.md for prerequisite commit audit and remaining build gates.
No active NUC or AV1 source changed. AV1 build still compiling modules during
this work. Production D/F and original installed modules restored.
