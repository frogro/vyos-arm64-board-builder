# RGA and Chromium decoder research — 2026-09-21

Research only; no live changes, production defaults or workflow changes.
Read together with sunshine/rga-investigation/README.md and
sunshine/decoder-investigation/README.md. Browser GPU rendering already tested
does not establish hardware video decoding.

## RGA BT.709

Rockchip's official librga changelog records RGB-to-YUV BT.709 limited support
for RGA2 in 1.10.0, requiring vendor driver 1.3.0; 1.10.4 records another
BT.709 limited correction on some chips, recommending driver 1.3.9:
https://github.com/airockchip/librga/blob/main/CHANGELOG.md

This is a concrete history to investigate, NOT proof of the same bug or a ready
patch for our media/V4L2 rockchip-rga driver. Installing librga alone does not
change our V4L2 conversion implementation. Vendor driver version numbers do
not describe our upstream media driver.

Our measured BT.709 gray values suggest nearly full-range luma with limited
clipping; this remains a hypothesis. Full/limited requests currently produce
identical output. Audit matrix selection, coefficient/offset programming,
clipping and capability differences against vendor rga2_reg_info.c. Trace the
actual changes behind the release notes before selecting a backport. Negotiate
and return colorspace, ycbcr_enc and quantization correctly. Reject unsupported
combinations instead of silently claiming support.

Reference:
https://github.com/rockchip-linux/kernel/blob/develop-6.1/drivers/video/rockchip/rga3/rga2_reg_info.c
https://github.com/airockchip/librga/blob/main/docs/Rockchip_FAQ_RGA_EN.md

Acceptance: known RGB patches and gray ramp, BT.601/709 each full/limited,
numeric comparison to matching software references, metadata verification,
then stream performance. Keep swscale until correctness passes.

Forum lead (HDMI input/conversion, not evidence of our precise range bug):
https://forum.radxa.com/t/rock-5b-poor-hdmi-in-performance-with-bgr3-color-format-and-colorspace-conversion/22191

## Chromium routes

### First assess upstream V4L2 stateless decoder backport

Collabora reports merged VDPU381/RK3588 H.264 and HEVC support, with decoder
sources, DT bindings/nodes, new HEVC RPS UAPI and reset/IOMMU recovery. GStreamer
1.28 supports the new controls. Our 6.18.50 tree does not gain this automatically.
Identify exact upstream commits and dependencies before choosing a backport or
separate newer test kernel. Do not assume a copied C file and DT node suffice.
https://www.collabora.com/news-and-blog/news-and-events/rk3588-and-rk3576-video-decoders-support-merged-in-the-upstream-linux-kernel.html

Community experiments report Chromium 150 V4L2 decoding on RK3588 with a
particular newer kernel/Mesa/browser combination. This is a candidate to
reproduce, not proof for our Debian Chromium or all codecs. The repository
also contains downstream kernel pieces; do not call the whole setup upstream.
https://github.com/dongioia/rock5bplus-rkvdec2

### MPP plus VA-API bridge (alternative experiment)

rockchip-vaapi PR #2 adds Chromium compatibility, fixes chroma plane offsets
and H.264 B-frame stalls. Its optional RGA NV12-to-NV12 stride copy is distinct
from our RGB-to-NV12 BT.709 conversion. Requires a functioning MPP decoder,
which our current kernel/DT does not provide. PR was open when reviewed.
https://github.com/woodyst/rockchip-vaapi/pull/2

Open issue #3 reports memory-bound problems, including claimed hardware/ASAN
reproductions, and HEVC behavior dependent on MPP version. Findings have not
been independently reproduced here. Audit/fix before adoption; do not copy
global sandbox-disabling packaging from the project's Firefox instructions.
https://github.com/woodyst/rockchip-vaapi/issues/3

### MPP through libv4l-rkmpp (additional fallback)

Rockchip's Jeffy Chen maintains a V4L2 wrapper explicitly for patched Chromium.
The README requires custom browser patches and lists Chromium-specific hacks.
This entails maintaining browser integration, not merely installing FFmpeg.
https://github.com/JeffyCN/libv4l-rkmpp

## Test order / generic profile F

1. Compare complete upstream decoder backport requirements against vendor MPP
   port requirements; prefer standard V4L2 interfaces if feasible.
2. Prove decoding outside Chromium, with known H.264 then HEVC streams and
   supported userspace. Exercise seek, resolution changes and error recovery.
3. Test actual kiosk Chromium in isolated container, preserving sandbox and
   granting only discovered devices. Verify browser build/backend support.
   Keep X11 as baseline; assess DMA-BUF import/render compatibility separately
   rather than assuming Wayland alone enables decoding.
4. Record per-video decoder diagnostics (media-internals), driver activity,
   dropped frames, CPU use and visual correctness. chrome://gpu support alone
   is insufficient. Test VP9/AV1 separately for YouTube; HEVC success does not
   imply YouTube acceleration.
5. Detect capabilities instead of board names; platform-specific kernel/DT
   remains necessary. Retain software fallback and pin tested versions.

Chromium's own verification documentation:
https://chromium.googlesource.com/chromium/src/+/HEAD/docs/gpu/vaapi.md

Next engineering tasks are RGA vendor-fix tracing and upstream decoder commit
dependency audit. None of the researched paths is yet a validated live fix.
