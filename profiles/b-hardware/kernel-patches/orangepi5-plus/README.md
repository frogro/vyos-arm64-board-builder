# Orange Pi 5 Plus peripheral backports

Applied only for Orange Pi 5 Plus with profile B, after the shared MPP provider.
The patch path and content hash participate in the kernel preparation cache key.
Other boards do not opt in. SD/eMMC and ISO use the same prepared kernel payload.

1. `0001`: USB-C DP0 video via VP2. FUSB302/PHY0 switch and HPD logic already
   exists in 6.18.50. No fictitious DP audio card: this dw-dp driver has no audio
   implementation. DP video still requires a physical adapter/monitor test.
2. `0002`: RK3588 VDPU381 V4L2 decoder and HEVC controls from the exact pinned
   ROCK source archive used by the Panthor test build. Includes the archive's
   H264/HEVC fixes and VP9 experiment; do not infer VP9 acceptance. MPP decoder
   remains disabled, avoiding two drivers claiming the decoder. SRAM and IOMMU
   nodes accompany the decoder. Archive/file provenance is in the JSON file.
3. `0003`: experimental RK3588 CSI/VICAP/ISP2 modules, CSI2 receiver, generic
   V4L2 ISP helpers and DT nodes. Source:
   https://git.ideasonboard.com/epaul/linux/src/commit/532f326bf40443ad6c656f9482cc18125a9b2dc3
   This is the developer's v7.0 RK3588 ISP2 branch. Only the required new helpers,
   two metadata formats and RKISP1_V30 enum are added; existing RKISP1 parameter
   ABI/types are retained. The public RFC is:
   https://lists.infradead.org/pipermail/linux-arm-kernel/2026-April/1123416.html
   All camera/ISP nodes remain disabled. A sensor-specific board overlay must
   provide supplies/clocks/lane mapping and the sensor->CSI->VICAP->ISP graph.
   No particular camera, libcamera tuning, or complete capture pipeline is
   claimed as tested. Native HDMI RX remains independent.

Validation performed:
- All three patches apply with fuzz=0 against fresh v6.18.50 files plus MPP DT.
- AArch64 cross compilation: linked rockchip-vdec.o, rockchip-cif.o,
  rockchip-isp2.o, dw-mipi-csi2rx.o and V4L2 core; Orange Pi DTB compiles.
- Final Kconfig retains CIF/ISP2/CSI2RX/CSI PHY as modules. V4L_PLATFORM_DRIVERS
  must be enabled; otherwise Kconfig silently omits these optional modules.
- DTB contains enabled DP0 and RK3588 decoder nodes, disabled CSI/ISP nodes.

Pending: complete kernel link/modpost and image build, Orange Pi live probe and
hardware acceptance. DP audio needs an additional driver port; enabling SPDIF
or adding a sound-card DT node alone does not supply it. Existing fallback image
must be retained for first boot. No live kernel was replaced by this change.
