# Orange Pi 5 Plus peripheral backports

Applied only for Orange Pi 5 Plus with profile B, after the shared MPP provider.
The patch path and content hash participate in the kernel preparation cache key.
Other boards do not opt in. SD/eMMC and ISO use the same prepared kernel payload.

1. `0001`: USB-C DP0 video via VP2. FUSB302/PHY0 switch and HPD logic already
   exists in 6.18.50. Audio is added separately by 0004. DP video still
   requires a physical adapter/monitor test.
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
- All four patches apply with fuzz=0 against fresh v6.18.50 files plus MPP DT.
- AArch64 cross compilation: linked rockchip-vdec.o, rockchip-cif.o,
  rockchip-isp2.o, dw-mipi-csi2rx.o and V4L2 core; Orange Pi DTB compiles.
- Final Kconfig retains CIF/ISP2/CSI2RX/CSI PHY as modules. V4L_PLATFORM_DRIVERS
  must be enabled; otherwise Kconfig silently omits these optional modules.
- DTB contains enabled DP0 and RK3588 decoder nodes, disabled CSI/ISP nodes.

Pending: complete kernel link/modpost and image build, Orange Pi live probe and
hardware acceptance. DP audio is now backported but not hardware-tested. Existing fallback image
must be retained for first boot. No live kernel was replaced by this change.

## DP audio backport (0004)

Source: Sebastian Reichel (Collabora), v11 21/21, 2026-08-06:
https://lists.openwall.net/linux-kernel/2026/08/06/1875
SDP locking and slot lifetime adapted from patches 16/21 and 18/21 of:
https://lists.openwall.net/linux-kernel/2026/08/06/1867

This is a focused 6.18.50 port, not the entire newer bridge/PHY series.
The existing driver keeps APB/AUX clocks active while bound; runtime-PM calls
from the newer series are therefore not copied. Audio state is mutex protected
including video enable/reset, SDP buffers are zeroed, register-read errors are
checked and allocation error codes survive cleanup. Audio clocks remain balanced
across repeated prepare/shutdown; audio registers are restored after a modeset.
The internal SPDIF2 route feeds DP0 with DAI argument 1. HDMI and analog routes
are unchanged. Rockchip SPDIF is a profile-B module and a readiness requirement.

The newer out-of-band HPD-cache patch is not applied:
https://lists.openwall.net/linux-kernel/2026/08/21/1449
Our 6.18 PHY uses hardware HPD, caches dp_sink_hpd_cfg and replays it when DP
powers on. It does not call drm_connector_oob_hotplug_event. Importing that
cache alone would not fix this path. Cold boot with a connected monitor and
unplug/replug must still be tested; no blanket boot-race fix is claimed.

Validation: the four-patch chain applies with fuzz=0 to fresh stable v6.18.50
files plus shared MPP DT. AArch64 compilation passed for dw-dp, DRM bridge
connector/audio helper, rockchip_spdif and the Orange Pi DTB. Existing six
extended-network and ten hardware-provider tests pass. Full kernel link/modpost,
SD/ISO build and USB-C display/audio acceptance remain pending. Test stereo PCM
first, then repeated playback stop/start, modesets, hotplug and shutdown while
checking ALSA/DP errors. This change does not establish multichannel acceptance.
