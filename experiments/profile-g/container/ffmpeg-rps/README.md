# Private FFmpeg HEVC RPS backport

Apply only 0002 to jernejsk/FFmpeg 904a85173fab816bb3c30652300efa93f2333657.
Backported from Detlev Casanova (Collabora):
https://gitlab.collabora.com/detlev/ffmpeg/-/commit/a8eb4b006d055f0be43d4a03d87472d2f199f177

The original upstream diff, compatibility header provenance, software/hardware
pixel comparisons and H264 regressions are retained in
../../live-test/steamlink/ffmpeg-rps/. The build fails on patch drift and copies
this patch directory alongside the private decoder for installed provenance.

`0003-nv15-uapi.patch` includes `v4l2-nv15-compat.h` in capture negotiation.
Debian 6.12 build headers omit linear V4L2_PIX_FMT_NV15 even though the running
RK3588 kernel can produce it. The compatibility definition is identical to Linux
6.18 UAPI (https://github.com/torvalds/linux/blob/v6.18/include/uapi/linux/videodev2.h).
It only enables the existing FFmpeg format mapping; unsupported devices still
fail runtime negotiation. System headers and libraries are not modified.
