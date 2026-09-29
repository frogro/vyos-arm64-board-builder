# Chromium153 NV12 color import finding (test3)

Observed on unmodified Debian Chromium153, isolated Weston/Mali, both H264 and
HEVC1080p60 fixtures. Media tracks report BT709/limited. Frame1799 canvas PNG
mean absolute RGB difference vs FFmpeg BT709 reference ~[12.96,1.60,5.66].
Forcing the FFmpeg reference conversion to BT601 yields ~[0.72,0.05,0.83] for
HEVC, consistent with BT601 YUV conversion being used on the hardware-import path.
Controlled software H264 path mean difference vs BT709 reference ~[1.76,1.12,1.56].

Matching upstream source at exact153.0.8010.47:

- media/gpu/chromeos/mailbox_video_frame_converter.cc lines235–240 chooses
  external sampler for multi-plane Linux/ChromeOS frames.
- ui/ozone/common/native_pixmap_egl_binding.cc lines115–148: NV12/YV12/P010
  import sets EGL_YUV_COLOR_SPACE_HINT_EXT to REC2020 for BT2020_NCL, otherwise
  explicitly REC601. Full/limited range is selected separately. The source
  comment explains an existing ChromeOS DRM-overlay compatibility policy;
  BT709 is intentionally not selected here.

Sources:
https://chromium.googlesource.com/chromium/src/+/153.0.8010.47/ui/ozone/common/native_pixmap_egl_binding.cc
https://chromium.googlesource.com/chromium/src/+/153.0.8010.47/media/gpu/chromeos/mailbox_video_frame_converter.cc

This is strong evidence for a browser import-policy mismatch for our path;
not proof of a new kernel, decoder or Sunshine RGA CSC defect. Do not globally
replace REC601 with REC709: BT601 streams and ChromeOS/direct-overlay behavior
must remain correct. A future opt-in source change should use actual frame matrix
for a validated Linux compositing path and test both compositing and overlays.
No Chromium source patch for this finding is installed or built yet. Require
BT601/BT709, full/limited and software/hardware controls before promotion.
Physical HDMI screen comparison remains deferred per user request.
