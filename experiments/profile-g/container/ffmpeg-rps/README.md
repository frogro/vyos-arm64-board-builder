# Private FFmpeg HEVC RPS backport

Apply only 0002 to jernejsk/FFmpeg 904a85173fab816bb3c30652300efa93f2333657.
Backported from Detlev Casanova (Collabora):
https://gitlab.collabora.com/detlev/ffmpeg/-/commit/a8eb4b006d055f0be43d4a03d87472d2f199f177

The original upstream diff, compatibility header provenance, software/hardware
pixel comparisons and H264 regressions are retained in
../../live-test/steamlink/ffmpeg-rps/. The build fails on patch drift and copies
this patch directory alongside the private decoder for installed provenance.
