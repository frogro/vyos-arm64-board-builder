# D/F media dependency audit, 2026-09-22

Audit of tracked D/F experiments and their prerequisite commits, not a claim
that every experimental change is already included in a release image.

| Layer | Required/observed beyond individual driver patches | Evidence |
|---|---|---|
| Kernel and DT | Correct RK3588 stateless rkvdec/Hantro codec source, Kconfig, matching media UAPI, DT clocks/resets/IOMMU/power domains, selected modules | 8c61bea, a3056b5; VP9 4347725; AV1 test4 still building |
| Boot/initramfs | Include GPU firmware and dependencies when modules load early; matching DT/initramfs, preserve fallback | ec8eeed, 8e3262f; boot checks a3056b5 |
| GPU userspace | Panthor kernel + Mali firmware + compatible Mesa/Panfrost EGL/GBM/ANGLE rendering; DRM display card alone is insufficient | 7b755da, d317d80, 8aa65d9 |
| Container access | Decoder video node and matching media node, DRM render node, correct supplementary groups; discover capabilities/paths rather than fixed videoN/board names | ed2eb67, 2fd1184; physical test reproduced missing-render-group software fallback |
| Session/display | Wayland/Mali comparison path; production X11/glamor is separate; compositor seat/VT/DRM ownership and socket permissions matter | d317d80, 8aa65d9; physical seatd + Weston14 test |
| Chromium runtime | V4L2-enabled ARM64 build, AcceleratedVideoDecoder, AcceleratedVideoDecodeLinuxGL, PreferV4L2VideoAcceleration, Ozone Wayland, working ANGLE GLES; normal sandbox retained | 8aa65d9, b23c0ee |
| Chromium buffer reserve | Disabled-by-default non-low-delay stateless MMAP reserve candidate; live adapter verifies mechanism, not compiled implementation | 216a3b2, 748465b, 1c93db4 |
| Chromium 10-bit | NV15 format support across Chromium and ANGLE plus EGL capability gate; P010 is not an interchangeable alias | 3bc8cc1, 8a8c540; NUC c648b79 build incomplete |
| HEVC extended references | Kernel bounds checks are distinct from browser SPS/RPS generation; dedicated Chromium patch still separate from initial NUC candidate | 0179bf9, 8941c0f, chromium-rps/README.md |
| GStreamer validation | Isolated 1.28.7 core/base/bad, appsrc, parsers and v4l2codecs; explicit v4l2slh264dec/h265dec/vp9dec; native NV15 for bitexact10-bit checks | 4e1a42d; build-gstreamer.sh and Containerfile.gstreamer |
| Compositor timing | Weston headless timing correction and Weston16 comparison affect virtual benchmarks; not proof that physical DRM needs same change | d221f12, 651a5f1 |
| D/F stream encoding | Separate ffmpeg-rockchip/MPP/RGA userspace, scoped MPP/RGA devices and actual encoder availability; not browser V4L2 decoder | 0402a4f, 1415abe, 78a7446 |
| Packaging/update | Opt-in F assembly, CLI/host/runtime helpers, explicit firmware provider, persistent config/state and first-install/update checks | BUILD-INTEGRATION.md; 3a8debd |

GStreamer is a separate player/test pipeline. Installing it does NOT route
Chromium video playback through GStreamer and does not replace Chromium NV15,
SPS/RPS or capture-pool work. Profile D's GStreamer-MPP encoder is another path;
its color metadata and layout fixes must be packaged when that option is used.

The current reserve candidate excludes low_delay but is NOT yet restricted to
H264 by codec. A future gate can select H264 plus the affected V4L2 MMAP path,
with an opt-in and bounded allocation. Do not edit the active NUC source during
compilation or claim this additional gate is already compiled/tested. HEVC/VP9
have no established need for blanket extra slots. AV1 success would not remove
H264 input streams, NV15 support needs, or extended HEVC reference requirements.

Current tests use privileged isolated physical-display containers to establish
the path; release packaging must retain scoped device/capability access. No
production privileged-container default follows from a diagnostic launch.
