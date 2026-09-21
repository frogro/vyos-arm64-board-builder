# Decoder integration audit, 2026-09-21

The running test2 kernel and the HEVC Sunshine image do **not** establish video
hardware decoding. The following gaps were verified in the actual test2 source:

* `ROCKCHIP_MPP_RKVDEC2` exists in Kconfig and the Makefile names
  `mpp_rkvdec2.o` and `mpp_rkvdec2_link.o`, but their C sources and decoder headers
  are absent. The existing encoder patch includes compatibility shims and these
  declarations, not a complete decoder port. Enabling this option cannot build.
* The final test2 DTB lacks decoder cores and decoder IOMMU nodes. Power-domain
  and QoS nodes do not instantiate the decoder.
* The alternative upstream `rkvdec.c` in this source only matches
  `rockchip,rk3399-vdec`; enabling VIDEO_ROCKCHIP_VDEC does not add RK3588 support.
* Our FFmpeg static library build deliberately disables everything except the
  selected encoders and their dependencies. It disables programs and enables no
  decoder. Chromium uses its own media stack, not Sunshine's FFmpeg libraries.

## Pinned vendor comparison

See vendor-reference.json for the official rockchip-linux/kernel commit and
SHA256 of the examined files. Files were fetched for comparison only; they were
not copied into the kernel tree or applied live.

The vendor decoder also includes mpp_rkvdec2_link.h, SoC hack files, and BSP
OPP/system-monitor/IOMMU interfaces. Copying the two C files alone is insufficient.
Its RK3588 reset operations select rkvdec2_sip_reset. That function chooses SIP
or CRU reset based on CONFIG_ROCKCHIP_SIP. Existing local SIP/QoS compatibility
stubs must be audited against the actual selected reset/link paths; returning
success from a stub does not prove reset recovery works.

Vendor DT describes CCU, two decoder cores, five clocks per core, resets, decoder
IOMMUs, task queue 9, RCB/SRAM mappings and power domains. Its BSP-specific IOMMU
properties cannot simply be assumed to work with our upstream IOMMU driver.

## Required sequence before another decoder test kernel

1. Choose a complete, pinned decoder implementation and port its dependencies in
   a separate experimental patch. Keep the working encoder path intact.
2. Adapt matching SoC DT bindings, clocks, resets, IOMMU and RCB allocation.
   SoC-specific kernel descriptions are expected; runtime capability selection
   must not infer support from a board name.
3. Compile in a separate build directory; audit final config, DTB and module
   dependencies. Preserve test2 artifacts and boot rollback.
4. Exercise H264/HEVC decoding, reference frame output, repeated startup and error
   recovery with a matching standalone userspace decoder before browser changes.
5. Verify the specific Chromium/Qt media integration separately. A successful
   MPP/FFmpeg decode or Mali WebGL result alone does not establish browser decode.

No decoder activation, new test kernel, or new browser-decode claim accompanies
this audit. CPU video decoding remains the fallback.

## Isolated test3 backport, 2026-09-21

0001-experimental-upstream-rkvdec-backport.patch is an experimental delta on
the prepared 6.18.50 test2 source, not enabled by release builds. It overlays
the pinned v7.0 rkvdec driver, adds upstream HEVC extended SPS controls, applies
four subsequent HEVC bounds/RPS fixes, and adds RK3588 decoder/IOMMU/SRAM nodes.
Exact input blob hashes, fix commits and before/after file hashes are in
upstream-reference.json. The metadata-copy call retains the 6.18 third argument
(false). Existing encoder, GPU and audio changes remain in the base tree.

The complete patch passes a dry-run against the original source. Targeted
compilation of rkvdec, V4L2 core and rk3588-rock-5b.dtb succeeds with GCC15.2.
This is compile validation only: full link, live probe, reset/IOMMU recovery,
actual H264/HEVC decode and browser integration remain unverified.

Full build runs separately under user service vyarm-decoder-test3-build, -j1,
MemoryHigh=2G, MemoryMax=3G, Nice=10. Workspace:
/mnt/entwicklung/projekte/VyOS/arm/vyos-arm64-board-builder/tmp/kiosk-decoder-20260921
Config uses CONFIG_VIDEO_ROCKCHIP_VDEC=m and LOCALVERSION=-vyos-f-test3.
No test3 installation or reboot has occurred. No private signing keys belong
in this patch or repository.
