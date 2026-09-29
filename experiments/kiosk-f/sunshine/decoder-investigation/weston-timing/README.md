# Upstream Weston headless timing fix candidate

Upstream commit f36a0c2cb88a85bf8e0958fb4ca23b6e2d6d85c4 by Michael Olbrich:
https://github.com/wayland-mirror/weston/commit/f36a0c2cb88a85bf8e0958fb4ca23b6e2d6d85c4

The commit specifically fixes additional headless frame delay caused by
compositor repaint scheduling and rendering time. It uses the existing
weston_output_arm_frame_timer helper to schedule relative to expected vblank.
This matches our experimentally identified virtual-output timing sensitivity.

Current isolated browser image uses Debian weston14.0.2-1. Patch dry-run
passes against upstream14.0.2; compositor.c in that tag already supplies
the helper, so no kernel dependency is indicated. Weston16 contains the fix.

Status: compiled and tested in isolated image on2026-09-21. The patch is
upstream and board-independent; it changes only the Weston headless backend.
No kernel or Chromium changes needed for this improvement. Production kiosk
and D service remain unchanged. No physical-screen smoothness claim.

## Reproduce

From this directory, `podman build -t localhost/vyarm-kiosk:weston-timing-test3 .`
uses the existing browser-wayland-test3 image, Debian weston14.0.2-1 source
and build dependencies. Only headless-backend.so is copied into the final
runtime image; compiler/dependency upgrades stay in the build stage. The
original runtime libraries and browser are retained. Limit build memory/CPU
externally and use ninja-j1 as specified. Source package is version pinned,
APT build dependencies use configured repositories, so it is not a bit-for-bit
reproducible toolchain. Runtime image ID is recorded in results/image-id.

Use ../test-browser-performance.sh with identical fixtures and selected
video/media nodes. PERF_RUNS=1,PERF_REFRESH=60000, no repaint override.
Order: patched,original,patched-repeat. Each contains H264 and HEVC.

## Result:1800-frame1080p60 files,60Hz virtual output

| Backend | H264 HTML drops | HEVC HTML drops |
|---|---:|---:|
|original|685|671|
|patched first|262|7|
|patched repeat|272|5|

All ended1800 frames, V4L2VideoDecoder/platform=true, same sandbox/GPU/
Chromium/codec files. HEVC<0.4% drops; H264~15% remains. Whole browser+Weston
cgroup steady CPU H264~66% one core patched vs60% original; HEVC~56% both.
Rendering more frames can require more CPU; not a decoder-only benchmark.

This isolates a substantial headless timing defect. It is NOT a complete
H264 presentation fix. Separate SPS/RPS and BT709 import defects remain.
The initial20s WebRTC patched run also had one H264 freeze/50RTPdrops;
H265 had none. Matched repeat comparison required before promotion.

Matched20s WebRTC repeat (original then patched) completed:
H264 HTML drops425/1188→73/1184; HEVC389/1084→76/1156. Both codecs
in both repeat variants had0RTPframesDropped,0packetloss,0freezeCount.
The first patched H264 freeze did not recur; its evidence is retained, not
discarded. Short runs do not establish long-term reliability. All temporary
receiver/publisher containers and internal networks were removed.

Next work: investigate remaining H264 presentation losses and test actual
HDMI output separately. This patch is only for the isolated headless test
backend; do not add it as a supposed fix for the production X11 kiosk.
