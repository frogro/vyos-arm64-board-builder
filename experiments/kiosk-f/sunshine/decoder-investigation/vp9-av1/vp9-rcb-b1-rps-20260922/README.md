# Test3: VP9 + RCB + H264 B1 + HEVC RPS validation, 2026-09-22

Completed live without reboot on ROCK5B/6.18.50-vyos-f-test3. This remains
an isolated experiment; no installed modules, image defaults or workflows
changed. AV1 test4 source/build was not modified.

## Source and attribution

Base: ../vp9-live-20260922 four-part VP9 series plus original test3 safeguards.
EBUSY guard remains present to avoid mixing the earlier independent experiment.

- RCB: Detlev Casanova, Keep RCB to the correct size, v2 1/5:
  https://lists.openwall.net/linux-kernel/2026/08/10/1804
  Included diff applied with context offsets only. Checks dimensions each run
  and grows temporary buffers when needed. No multicore patches included.
- H264: Haotian Zhang, Fix memcmp() size in B1 reference list comparison:
  https://patchew.org/linux/20260901022310.12184-1-vulab@iscas.ac.cn/
  Included local diff implements upstream sizeof(entry)*count correction.
- HEVC: Michael Bommarito, validate HEVC EXT SPS RPS counts, v2 2/3:
  https://patchew.org/linux/20260527194737.1999409-1-michael.bommarito@gmail.com/20260527194737.1999409-3-michael.bommarito@gmail.com/
  Included local diff ports the missing shared-core validations. Existing64/32
  control dimensions and prediction-index guard retained. Does not generate
  missing Chromium SPS/RPS controls.

External build directory: tmp/vp9-rcb-b1-live-test3 beside other experiments.
Copy test3 drivers/media/v4l2-core into core/, apply included core patches,
copy VP9 external source and apply RCB patch. Top-level Makefile:
obj-m += core/ drivers/media/platform/rockchip/rkvdec/
Use matching source/O= test3 kbuild, M=this directory, ARCH=arm64,
CROSS_COMPILE=aarch64-linux-gnu-, CONFIG_VIDEO_ROCKCHIP_VDEC=m, -j1 modules.
Sign core/videodev.ko,core/v4l2-h264.ko,rockchip-vdec.ko with matching test3 key.
Do not include private key material in artifacts.

First separate builds failed to load rkvdec against rebuilt videodev due to
v4l2_fh/event symbol CRC differences (old kbuild symvers entries were zero).
No forcing or stripping versions: building the modules together resolved
export/import versions. Baseline services/modules restored on failure.

## Boundary and decoder tests

rps-try-probe.c uses only S_FMT and TRY_EXT_CTRLS, never starts hardware decode.
Static ARM64 build uses test3 UAPI v4l2-controls.h ahead of system includes.
All9 cases pass: ST64/LT32/negative16/sum16 accepted; ST65/LT33/negative17/
positive17/sum17 rejected with EINVAL. An initial probe omitted chroma_format_idc
and valid SPS controls were rejected too; setting valid4:2:0 corrected the
probe. No driver workaround was added for that harness error.

H264 and HEVC: three exact I420 reference comparisons each, explicit GStreamer
stateless hardware decoder, all pass. VP9 Profile0: all300 nativeNV12 frame
hashes match software reference. No software fallback in these pipelines.

Sandboxed Chromium153/Weston16, 1080p60,30seconds/1800frames each:

| Fixture | Dropped frames |
|---|---:|
| Original H264 B-pyramid |287|
| HEVC paired with original |3|
| VP9 repeated fixture |7|
| H264 no-B fixture |16|
| Same HEVC paired with no-B |3|

All ended, V4L2VideoDecoder and platform=true. Compared with VP9 baseline
263H264/4HEVC/11VP9 drops, this does not fix the H264 presentation problem.
Single-run differences cannot establish a smaller performance change.
No new relevant decoder/IOMMU fault; known ignored second core remains.

Shared videodev replacement required briefly stopping vyos-kvm-video.service
and unloading decoder/RGA/HDMI-RX/mem2mem/VB2-V4L2 dependencies. Kiosk stayed
active. Finally original installed modules restored, HDMI capture service
restarted, both D video and F kiosk services active, decoder S264/S265 only.
Script retains baseline restoration on exit and never force-unloads modules.

## Limits / next tests

RCB initial allocation and repeated fixed-size sessions exercised; in-session
resolution growth/shrink is NOT yet verified. Next targeted check should cover
that with reference frames and allocation traces. VP9 Profile2/10-bit/native
NV15 and patched Chromium import remain separate pending checks. No physical
screen validation, broad conformance or endurance claim. Combined test cannot
attribute any individual effect to one patch. H264 reference/presentation
lifetime investigation remains open.
