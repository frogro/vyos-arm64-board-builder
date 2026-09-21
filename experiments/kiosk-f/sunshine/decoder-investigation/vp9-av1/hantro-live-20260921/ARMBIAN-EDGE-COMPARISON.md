# Historical Armbian Edge release comparison

Inspected the actual release image, without booting or installing it. Download
passed the release SHA256SUMS check. Extracted partition read-only with debugfs;
no guest scripts executed. Full image remains outside Git in builder tmp.

Release: https://github.com/frogro/vyos-build/releases/tag/armbian-rock5b-dwc3-fix
Published 2026-08-07, kernel 7.1.7-edge-rockchip64, Armbian 26.08.0-trunk.
The release target `rolling` is not a kernel source revision. The image reports
Armbian build commit 815a50b664f97bcf8357f5e31e2b610603034c0e. This identifies
the recorded build framework; it does not exclude local source modifications.

## Artifact evidence

| Component | Historical Armbian image | Current test3 base / experiment |
|---|---|---|
| Hantro | CONFIG_VIDEO_HANTRO=m, ROCKCHIP=y | disabled in base config; signed external diagnostic module used |
| AV1 IOMMU | CONFIG_VSI_IOMMU=y, built-in symbols in System.map | absent in current test path |
| Device Tree | AV1 references iommu@fdca0000 | no AV1 IOMMU in current test path |
| CMA default | 128 MiB | 0 MiB configured default |
| AV1 resets | all four core + BIU resets | same four, diagnostic remove mask tested |
| Hantro remove order | clocks unprepare, reset assert, disable autosuspend, disable runtime PM | experimental PM ordering plus split-reset diagnostic |

The released hantro-vpu.ko imports vsi_iommu_restore_ctx and
 iommu_get_domain_for_dev. Its disassembly confirms the old remove ordering;
it does not contain our diagnostic fix. CONFIG values describe the image,
not a measured runtime allocation or successful playback on that image.

## Existing patch to evaluate

The recorded Armbian build commit includes Benjamin Gaignard's Verisilicon
IOMMU patch (Collabora, 2026-01-07):
https://github.com/armbian/build/blob/815a50b664f97bcf8357f5e31e2b610603034c0e/patch/kernel/archive/rockchip64-7.1/media-0007-add-verisilicon-AV1-iommu-driver.patch

It adds the IOMMU driver, DT association and AV1 decoder context restoration
before every frame. The driver is built-in in this patch because modular
combinations had symbol issues. A DT-only or config-only backport is therefore
insufficient. This is an upstream-author patch carried by Armbian, not a new
patch developed for our project.

The IOMMU path is a concrete next comparison for allocation/mapping behavior.
It is NOT yet evidence of a fix for either BIU reset timeouts or browser frame
drops. The same four reset lines and old remove order remain in this image.
Do not suppress PM errors or replace the current decoder with v6.7 wholesale.

## Next isolated test

1. Review/backport the matching IOMMU driver, DT and AV1 context-restoration
   changes together against our exact test3 source; build as an optional test.
2. Keep a separate control with the proven core-only remove-reset diagnostic.
3. Repeat load/unload and idle recovery, 300-frame software-reference hashes,
   then the same 120-second Chromium and GStreamer fixtures.
4. Measure allocated memory, PM warnings and frame drops. Do not promote to
   profile F defaults until restart/error paths and display output are tested.

No kernel switch, production workflow, image default or live kiosk modification
was made for this artifact comparison. Historical Armbian runtime behavior has
not been tested here.
