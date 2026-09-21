# Firefox ESR isolated decoder comparison

2026-09-21, ROCK test3. Image6e8448f953cc711d86feb21ef3d1c853f533b61bd7765527cd50a29851433757.
Debian Firefox140.16.0esr with libavcodec61/FFmpeg7.1.5. This tests the
Debian ESR package, NOT all newer official Firefox versions or patchedFFmpeg.
Container is based on the sameWeston16 image; Podman/OCI onROCK, not
installation intohost orproductionkiosk. Noexternalnetwork, normalFirefox
sandbox retained, userkiosk, explicitGPU+V4L2deviceaccess,1GiBmemorylimit.

Initial --kiosk launch failed before page load with Weston protocol error:
xdg_surface geometry(1x1) larger than configuredfullscreenstate(0x0).
The final probe uses a normal1920x1080window and reaches videoEOS.
Thus these numbers are decoder-capability checks, NOT directly equivalent
fullscreen presentation benchmarks againstChromium. HeadlessWeston has
no physicalmonitor; no claim about physicaltouch/HDMIusability.

| Setting | Codec | Decoder evidence | Dropped / total |
|---|---|---|---|
| Default | H264 | FFmpeg, IsHardwareAccelerated=0 |64/1800|
| Default | HEVC | FFmpeg, IsHardwareAccelerated=0 |43/1800|
| media.ffmpeg.v4l2.enabled=true | H264 | FFmpeg, IsHardwareAccelerated=0 |62/1800|
| media.ffmpeg.v4l2.enabled=true | HEVC | FFmpeg, IsHardwareAccelerated=0 |39/1800|

All four30second synthetic1080p60 runs reachedEOS. H264fixture hasB-pyramid.
ExplicitV4L2preference does not by itself establish hardwareoperation.
No hardwaredecode success here, so no no-pyramid performance claim needed.
Sources checked: https://bugzilla.mozilla.org/show_bug.cgi?id=1833354
(V4L2M2M implemented), https://bugzilla.mozilla.org/show_bug.cgi?id=1969297
(statelessHEVC integration stillopen; FFmpegdependency; PiSANDlimitations
not automatically applicabletoROCK). Do not generalizeVAAPI/statefulsupport
toourstatelessrkvdecpath.

Reproduce by buildingContainerfile inthisdirectory, copyingprobe.py and
wayland.sh tothe paths inrun.sh, then runningrun.sh ontheROCK withthe same
fixtures/devices. Versionpinning requiredforfuturecomparison; apt source
is mutable. ReducedpageJSONandselecteddecoderloglines committed. Full
stderr and initialfailedfullscreenattempt retainedinliveartifactdirectory.
No kernel/productionconfiguration/releaseworkflow changes.
