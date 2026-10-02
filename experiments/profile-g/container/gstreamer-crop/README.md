# HEVC conformance-crop copy optimization (profile G)

Pinned source: GStreamer gst-plugins-bad 1.26.2, SHA256
`cb116bfc3722c2de53838899006cafdb3c7c0bc69cd769b33c992a8421a9d844`.
Source: https://gstreamer.freedesktop.org/src/gst-plugins-bad/gst-plugins-bad-1.26.2.tar.xz
Upstream function:
https://github.com/GStreamer/gstreamer/blob/1.26.2/subprojects/gst-plugins-bad/sys/v4l2codecs/gstv4l2codech265dec.c

The stateless HEVC decoder uses GstVideoConverter for conformance-window crops.
For linear NV12 with crop origin (0,0), no scaling and unchanged format, use
GstVideoFrame's stride-aware visible-plane copy instead. The source buffer and
its metadata remain unchanged; only a local mapped-frame view is resized.
Nonzero origins and other formats retain the original converter. This does not
remove the necessary output copy, implement zero-copy display, or change input
resolution to 1088. DMA-BUF map/unmap synchronization stays unchanged.

The G container builds and installs only libgstv4l2codecs.so. Core GStreamer,
codec libraries, profile D's cached RGB/BGR capture helper, profile F and Steam
Link's FFmpeg/V4L2-Request path are unchanged. The exact GStreamer core version
is checked at build and runtime-image assembly. Source checksum and patch
application are mandatory. Set VYARM_GST_HEVC_CROP_COPY=0 in the receiver process
environment to select the original converter for diagnosis. Default is enabled.
This is our local patch, not an upstream-accepted fix.

## Orange Pi live verification, 2026-09-30

Kernel 6.18.50-vyos; original G runtime g-7f8f7d8; rkvdec /dev/video2.
Tests ran in temporary containers, without replacing the active receiver.

- HEVC 1920x1080, coded 1920x1088, 180 frames / 3 seconds: unpaced
  gst-launch -> fakesink sync=false fell from approximately 5.1s to 0.567s.
  This is decode/copy throughput, not measured display latency.
- Per-frame SHA256 comparison against software decoding: all 180 NV12 frames,
  sizes, PTS and duration match. Same comparison against the patched plugin
  with optimization disabled also matches. Hashing runs took 1.19s enabled,
  5.81s disabled; hashing overhead is included.
- Nonzero crop control (left=8, top=4): all 180 frames, caps, sizes and timing
  match the original distribution hardware plugin. Software avdec_h265
  exposed a different width for this fixture, so it was not a valid oracle
  for that control. No general arbitrary-crop correctness claim is made.
- No HDMI presentation or audio synchronization acceptance is implied by
  these throughput and pixel tests. The new complete image needs its normal
  post-install integration checks.

The complete pinned build/install recipe was also executed natively on the
Orange Pi. Its staged plugin links to the unchanged distribution libraries;
all 180 HEVC frames match the initial patched binary. Hantro H.264 reached EOS
without error with that same staged plugin.
