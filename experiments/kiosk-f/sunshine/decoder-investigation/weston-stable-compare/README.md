# Stable Weston comparison and H264 reorder isolation

Production kiosk inspected2026-09-21: touch-reconnect-20260920 image
177f8d154126..., Chromium153.0.8010.47, Mesa25.0.7-2+deb13u1, Xorg and
Sunshine. No Weston installed/running. This is distinct from our original
comparison image containing Debian Weston14.0.2. No production video replay
or physical-screen change performed here.

Current upstream stable release verified as16.0.0:
https://wayland.freedesktop.org/releases.html

Run bash fetch-source.sh, then podman build using Containerfile. Weston16
installed into/opt/weston16 atop the same original browser runtime. New
wayland-protocols1.46 XML files needed for build; not a GPU/kernel/runtime
Wayland upgrade. GL/headless test build deliberately omits DRM and other
backends. This is NOT a replacement production image. Runtime browser, Mesa
and decoder kernel remain unchanged. Source archives hash checked.

Additional upstream audit:
- f36a0c2cb88a: proven headless frame-timer correction, included in16.
- c3af35c977de: fixes empty callbacks for Firefox/EFL after a dirty-bit
  optimization; not evidence of an H264-specific Chromium fix.
- 8c3112404bbc and9669073fe8f4 are later main-branch refactorings, not
  established performance fixes to backport blindly.
https://github.com/wayland-mirror/weston/commit/c3af35c977de616f238479f1911c48f62c49a883

H264 no-B fixture: same testsrc2,1920x1080@60,30s,libx264fast2threads,
8Mbps target/maxrate,8Mbpsbufsize,BT709limited,yuv420p,keyint60. Change
bframes3→0. FFprobe confirms bothHigh1800frames,bitrate8.091vs8.094Mbps;
reorder depth2→0. This isolates an encoder structural change, not identical
compressed bytes or identical quality. HEVC fixture retained as control.


## Results, 2026-09-21, completed 18:05 Europe/Berlin

All six runs ended, 1800 frames, 1920x1080 at 60 fps, with
V4L2VideoDecoder and platform=true. Counts below are HTML presentation
frame drops, not proof of decoder bitstream errors. Single runs per cell.

| Runtime | H264 structure | H264 drops | HEVC control drops |
|---|---|---:|---:|
| Weston 16 stable | B-frames=3 | 267 | 6 |
| Weston 14 + upstream timing patch | B-frames=0 | 6 | 6 |
| Weston 16 stable | B-frames=0 | 11 | 7 |

Previous patched-14 B-frame runs had 262 and 272 H264 drops. Stable 16
therefore does not resolve that residual problem. Eliminating B-frames is
strong evidence to investigate H264 reordering, reference-buffer lifetime,
output queue readiness and timestamps across Chromium/V4L2/driver. It does
not identify the faulty layer or prove that all B-frame streams fail.
Whole browser/compositor CPU on stable16 falls from 65.98% of one core to
58.40% for no-B H264. HEVC is 56.53–56.69%. These are not decoder-only CPU
measurements. No user video needs to be re-encoded on this evidence alone.

HEVC ordinary playback is confirmed in this isolated test configuration;
known SPS/RPS conformance and color-import limitations remain. Production
X11 playback was inventoried but not benchmarked against these headless
runs. Physical display and long-running playback validation remain open.

Built image: localhost/vyarm-kiosk:weston16-test3
SHA256: 78d07b3207e76a06235001f8d16001d04c0c99fedd0fa8e3d8b3c89db49a631a
Build and comparison services finished successfully. D/F remain active;
only production kiosk-test container remains running. No release workflow,
production container configuration or kernel changed by this comparison.

No-B fixture generation (synthetic, not included in repository):

```sh
ffmpeg -hide_banner -nostdin -n \
  -f lavfi -i testsrc2=size=1920x1080:rate=60 -t 30 \
  -c:v libx264 -preset fast -threads 2 \
  -x264-params bframes=0:keyint=60 \
  -b:v 8M -maxrate 8M -bufsize 8M -pix_fmt yuv420p \
  -color_primaries bt709 -color_trc bt709 -colorspace bt709 -color_range tv \
  test-h264.mp4
```
