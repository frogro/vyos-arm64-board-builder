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

Status: source audit and dry-run only. NOT compiled, installed or live-tested.
Next: build only in an isolated container, compare original/patched at60Hz
and default repaint-window7 on identical1080p60 H264/HEVC fixtures. Retain
original image, Chromium, decoder devices and sandbox. No physical kiosk
change. A successful timing fix would not resolve separate SPS/RPS or color
import findings.
