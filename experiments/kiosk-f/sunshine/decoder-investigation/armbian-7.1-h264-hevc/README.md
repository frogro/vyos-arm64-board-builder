# H.264 / HEVC: historical Armbian 7.1.7 comparison

Compared all 22 rkvdec files at upstream stable tag v7.1.7 against the actual
6.18.50 test3 source (which already carries a v7.0 decoder backport and fixes).
File blob IDs, URLs and both SHA256 values are in source-comparison.json.
Armbian patch inventory is pinned to image-recorded build commit
815a50b664f97bcf8357f5e31e2b610603034c0e. Local modifications to the historical
build cannot be excluded solely from this metadata. Checked the actual
released rockchip-vdec.ko disassembly as additional evidence.

## Findings

1. All H264-specific files, shared RCB code, registers, CABAC, and rkvdec.h
   are byte-identical to upstream v7.1.7. No new B-pyramid/reference-list fix
   emerges from these files. Current buffer reuse measurements still point
   to a userspace/reference/output scheduling investigation; they do not
   establish a single proven cause.
2. Armbian carries Jianfeng Liu's patch removing vb2_is_busy from rkvdec_s_ctrl
   (2025-09-04), explicitly described as addressing Chromium green screens
   and requiring further investigation. The released module's disassembly
   directly updates image_fmt and resets the format, without the busy-return
   path. Our test3 retains that check. Patch dry-run succeeds unchanged.
3. This path responds to SPS image-format changes (chroma/bit depth), including
   possible initial negotiation. It is not a general buffer-count or frame
   pacing adjustment. A constant 8-bit 4:2:0 B-pyramid stream does not change
   image format per B-frame. Hence this is primarily a negotiation/Main10
   candidate, not an established cure for the measured pyramid drops.
4. HEVC differences mostly reflect safeguards ALREADY added to our backport:
   tile bounds helpers, PPS index checks, RPS index validation and control
   dimensions 64/32 instead of upstream tag's 65/65. Retain these safeguards;
   replacing the full driver with v7.1.7 would lose them. DIV_ROUND_UP changes
   and the 6.18 metadata-copy API adaptation are not new speed optimizations.
5. Missing Chromium SPS short/long-term RPS submission is a userspace problem.
   A newer kernel or removing EBUSY does not supply those absent controls.
   Continue the separately planned Chromium SPS/RPS build and conformance
   fixtures. Do not mark H265 generally validated from ordinary clips.
6. Armbian's RK356x DT/rkvdec2 patch and Hantro H264 disable for RK3568 are
   relevant for those SoCs, not a ROCK 5B fix to transplant indiscriminately.
7. AV1 VSI-IOMMU is a different block. H264/HEVC RKVDEC already has its own
   IOMMU/SRAM path in test3. Do not infer benefits to these codecs from test4's
   AV1 IOMMU addition without separate evidence.

## Next controlled tests

- Instrument rkvdec_s_ctrl return values and format changes during the known
  H264 pyramid/no-pyramid, HEVC Main8 and Main10 fixtures. Establish whether
  -EBUSY actually occurs before attributing a problem to this check.
- Separate diagnostic module with only Armbian's busy-check delta; compare
  negotiation success, NV12/NV15 output, hashes and dynamic SPS changes.
  Removing a guard needs validation that buffers still match the new layout.
- Keep existing HEVC bounds/RPS safeguards and Chromium control work intact.
- Do not change the running IOMMU build mid-compilation or mix unrelated
  changes into its first AV1 comparison. No patch applied to live rkvdec here.

Sources:
https://github.com/gregkh/linux/tree/v7.1.7/drivers/media/platform/rockchip/rkvdec
https://github.com/armbian/build/blob/815a50b664f97bcf8357f5e31e2b610603034c0e/patch/kernel/archive/rockchip64-7.1/media-0002-media-rkvdec-remove-vb2_is_busy-check-in-rkvdec_s_ct.patch

This comparison concerns video DECODE for Chromium, not Sunshine MPP ENCODE.
For profile F it concerns kiosk video playback; for D only a playback/browser
path using this decoder can benefit. It does not automatically accelerate
HDMI capture or its H264/H265 encoder.

## VP9 follow-up

The inspected Armbian 7.1 image enables CONFIG_V4L2_VP9=m, but that helper is
not proof of RK3588 VP9 support. At v7.1.7, rockchip,rk3588-vdec selects
vdpu381_variant, whose coded formats are HEVC and H264 only. The existing
rkvdec-vp9.c is byte-identical to test3 and belongs to the older supported
variant; it is not wired to VDPU381. The pinned Armbian 7.1 patch inventory
contains no VDPU381 VP9 addition. Thus this image/source comparison provides
no additional RK3588 VP9 backend. Historical image runtime not tested here.

The separate VDPU381 VP9 candidate and its conformance limits remain described
in ../vp9-av1/RESEARCH-20260921.md. Follow with Profile0 8-bit reference tests,
then Chromium, before Profile2/NV15. AV1-IOMMU test4 does not add VP9 support.
