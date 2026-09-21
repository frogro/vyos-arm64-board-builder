# Optional AV1 IOMMU test4 build

Purpose: compare the Armbian AV1 IOMMU path against test3 using the same
fixtures and reset diagnostic. This is an experiment, not a profile default.

## Provenance

Original driver: Benjamin Gaignard / Collabora, GPL-2.0, carried by Armbian.
Recorded Armbian build commit: 815a50b664f97bcf8357f5e31e2b610603034c0e.
The 7.1 release driver initially fails two attach_dev callback type checks on
6.18. The corresponding rockchip64-6.18 patch at the same Armbian commit has
exactly those two signatures adapted (unused old-domain argument removed).
The test driver is byte-identical to that existing 6.18 variant, not a new
independent IOMMU implementation.

Source:
https://github.com/armbian/build/blob/815a50b664f97bcf8357f5e31e2b610603034c0e/patch/kernel/archive/rockchip64-6.18/media-0007-add-verisilicon-AV1-iommu-driver.patch

## Reproduction

On a separate exact test3 source/output copy:

1. Apply armbian-av1-iommu-test3-backport.patch. Includes the driver/header,
   Kconfig/Makefile integration, AV1 DT association and per-frame context
   restoration. Kconfig/Makefile context adapted to our source.
2. Apply existing hantro-pm-teardown-test.patch,
   hantro-pm-stage-diagnostics.patch and hantro-av1-split-reset-test.patch.
   Do not additionally apply the old omit-all-reset causal patch.
3. Set LOCALVERSION=-vyos-f-test4-av1-iommu, VSI_IOMMU=y,
   VIDEO_HANTRO=m, VIDEO_HANTRO_ROCKCHIP=y, then olddefconfig.
4. Keep CMA_SIZE_MBYTES=0 for the first comparison. Changing it simultaneously
   to Armbian's 128 would confound the IOMMU comparison.
5. Cross-compile the IOMMU object, Hantro directory and ROCK 5B DTB before
   the full Image/modules build. Use one job on this memory-limited ThinkPad.

The split-reset option remains opt-in, default -1. A live experiment must
prevent automatic Hantro probing before selecting mask=3 and exposing only
AV1. Do not install this as an ordinary unattended production boot.

## Required runtime checks (pending)

- One-shot boot with verified existing fallback; original default unchanged.
- Verify IOMMU binding/group, Hantro domain and power transitions.
- Separate control for reset policy, repeated unload/load and idle recovery.
- Three 300-frame NV12 hash comparisons against the software reference.
- Same 120-second GStreamer throughput and Chromium/Wayland playback tests.
- Capture memory usage, warnings, dropped frames and thermals.
- Verify kiosk, touch and HDMI output independently before any promotion.

Static review also leaves error-path/lifetime handling and zero-cell IOMMU
specifier handling for scrutiny. Merely compiling or copying the Armbian
patch is not proof of runtime correctness or browser performance.

## Build status

Targeted IOMMU object, complete Hantro directory and ROCK 5B DTB compile passed.
No compiler warnings in the successful targeted build log. Full Image/modules
build started separately as user service vyarm-av1-iommu-test4-build, one job,
MemoryHigh=1500M, MemoryMax=2500M, MemorySwapMax=256M. No auto-install or reboot.
Live tests above remain pending the full build and fallback preparation.
