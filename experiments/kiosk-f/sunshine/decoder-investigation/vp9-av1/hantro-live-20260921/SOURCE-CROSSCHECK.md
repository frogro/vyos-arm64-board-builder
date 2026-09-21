# RK3588 source cross-check, 2026-09-21

## Collabora / supplied PDF

https://gitlab.collabora.com/hardware-enablement/rockchip-3588/notes-for-rockchip-3588/-/blob/main/mainline-status.md

Pinned notes commit: 7a0ab8f7589bd146b18ec4e6dbb2bc0ece986be4.
Web/raw endpoint served a bot challenge; public Git clone succeeded. Reviewed all
four pages of the user's Firefox PDF visually; media table and relevant fixes
match the repository notes. The table distinguishes SoC support from board DT.

Actual diff comparison against local test3 source, not inferred from version:

| Upstream change | Commit | Local test3 |
|---|---|---|
| AV1 CDEF computation | e0f99b810e1181374370f91cd996d761549e147f | Present |
| AV1 tx-mode translation | cb3f945c012ab152fd2323e0df34c2b640071738 | Present |
| AV1 tile-info allocation size | a505ca2db89ad92a8d8d27fa68ebafb12e04a679 | Present |
| Missing HEVC ST/LT RPS pointer clearing | daa87ca42652af0d6791ef875e3c4d724b099f22 | Present |

Thus do not propose these four again as missing fixes. AV1 IOMMU is listed as
7.2-rc1; our tested AV1 DT node lacks an IOMMU association. VP9 VDPU381 is
listed as a submitted patch, separately from existing AV1 VDPU981 support.
RGA3 multi-core, decoder multi-core, HDMI-RX audio and V4L2 usage stats are
additional leads for D/F, not required changes or validated backports yet.

## Joshua Riek

https://github.com/Joshua-Riek/ubuntu-rockchip
Commit 38dfb49536f6952bdac2efc6d28fe14a3e7d258d, archived 2026-04-29.
README documents Rockchip vendor kernels 5.10/6.1 and accelerated Chromium.
Useful reference for the full vendor userspace/kernel combination; does not
establish drop-in compatibility with our 6.18 V4L2 path. Inspect actual package
sources/patches before transferring claims about browser decode.

## Same-SoC boards / complementary sources

https://github.com/mack42/OrangePi5Pro
Commit 5e94d087d0dd8734c83fc0c3e284a8dd2999dacc.
RK3588S recipe advertises VA-API AV1 via woodyst/rockchip-vaapi. This conflicts
with the previously inspected driver revision not advertising AV1; README/vainfo
claims alone are not playback proof. Recheck matching revisions before adopting.
Orange Pi 5 Plus (RK3588) is a closer SoC comparison to ROCK 5B; board-specific
DT wiring, power domains and clocks must still be checked.

https://github.com/yisding/rock-5b-ysp/tree/main/kernel-drivers/patches/forward-port-rk3588
Commit 69a3abbfdc3bee728c10df3c28ecfd9efdfd464a.
A 97-patch vendor MPP/RGA/AV1 forward-port for 6.18, including Verisilicon IOMMU
provider, DT wiring and lifecycle hardening. Relevant comparison material,
NOT the same driver path as Hantro V4L2; do not apply wholesale alongside it.

https://github.com/dongioia/rock5bplus-rkvdec2
Previously pinned 2c67fd3a3fde501d3f90082ad7f1c849d4f2d6cc remains the
separate V4L2/VP9/IOMMU lead.

## Next bounded work

1. Analyze AV1 remove/unbind/power-domain lifecycle before another live probe.
2. Identify exact Chromium initial-decode failure and tiled VT12 handling.
3. Compare appropriate upstream VSI IOMMU + DT changes and allocation needs.
4. Continue VP9 separately; preserve production paths and gate by hardware
   capabilities/compatible revisions rather than board-name-only selection.

## Teardown candidate found and compiled (~23:52)

https://lists.openwall.net/linux-kernel/2026/07/22/2001
Message-ID 20260722160820.2401-1-tharitt97@gmail.com, Tharit Tangkijwanichakul.
Reviewed-by Benjamin Gaignard (Collabora), reply:
https://lists.openwall.net/linux-kernel/2026/07/23/1947

The report describes RK3588 SError in hantro_remove through power-domain access
after reset assertion. Our test3 has exactly that ordering. The test backport
moves PM cleanup before reset assertion in remove and the probe failure path.
This is strong circumstantial evidence, not proof of our unlogged freeze.

Validation: git apply --check against unmodified exact test3 source passes;
external module rebuild with matching kernel output, MODVERSIONS, GCC15.2
and -j2 passes. Modified only the external experimental source copy.
Patch stored as hantro-pm-teardown-test.patch; not added to production kernel
recipe, not signed/deployed/loaded in this follow-up. No claimed runtime fix.

## Important correction to the format hypothesis

Although native AV1 buffers are VT12/NV12_4L4, rk3588_vpu981_variant also
registers rockchip_vpu981_postproc_fmts and hardware postprocessor operations.
That list includes linear NV12 and NV15. Therefore absence of VT12 in Chromium
does NOT alone prove a browser patch is needed. The next live probe should
request video/x-raw,format=NV12 directly from v4l2slav1dec (without inserting
videoconvert), inspect negotiated buffers, and retain Chromium verbose logs
for the first-decode failure. Allocation pressure remains another candidate.

## Test prerequisite after cold boot

Cold boot selected production 6.18.50-vyos, not the one-shot test3 entry.
The test3-signed JPEG module was rejected by signature validation; no module
loaded and temporary driver overrides were cleared. Future probe scripts must
check uname -r BEFORE any device changes. Verified test3 boot Image hash and
existing modules directory, then selected existing one-shot GRUB test3 entry
for the follow-up; permanent production default remains unchanged.

## Power-domain follow-up, 2026-09-22

The ACK error originates in rockchip_pmu_set_idle_request(): the expected ACK
depends on the requested idle direction. Existing error text omits that direction;
therefore the log alone does not establish power-on versus power-off failure.
The error can occur during asynchronous generic domain teardown as well as
probe. Prior wording attributing it specifically to activation is provisional.

The patched remove still asserts all AV1 resets, including A/P BIU resets,
after disabling runtime PM. Subsequent generic domain detach/idle handshakes
may interact with asserted bus-interface resets. This is a hypothesis, not a
verified root cause; do not remove resets or bypass power-domain checks blindly.

Relevant current sources checked:
* https://lists.infradead.org/pipermail/linux-rockchip/2026-September/076945.html
  Shawn Lin v3: propagate of_clk_get errors other than -ENOENT on attach.
  Local source lacks this robustness fix. No evidence of missing/deferred AV1
  clocks in this test, so it is not established as the ACK-timeout fix.
* https://lists.infradead.org/pipermail/linux-rockchip/2026-September/076561.html
  Optional domain-reset cycling, specifically motivated by RK3576 NPU.
  Requires reset ownership/DT changes; not a drop-in RK3588 AV1 fix.
* https://lists.infradead.org/pipermail/linux-rockchip/2026-September/076962.html
  Follow-up review; does not validate applying this to RK3588 AV1.

Read-only live check ~00:09: AV1 domain off-0, no AV1 device driver runtime-PM
attachment, host reachable. NUC build watchdog running with zero retries.

Prepared logging-only module patch hantro-pm-stage-diagnostics.patch after
the teardown backport. Logs probe/reset and each remove PM/reset boundary;
adds no MMIO reads or PM transitions. Exact test3 external rebuild passes.
Not signed, loaded, installed, or integrated into production.

Before the next controlled probe: capture kernel journal continuously to
ThinkPad; wait for actual registered device; stop on any domain warning.
Compare warning timestamps with remove stages; if outside them, instrument
the built-in PM-domain idle direction/caller in a separate test kernel.
A watchdog timer cannot recover a hard kernel hang; retain normal-boot fallback.


### Reset assertion control experiment (2026-09-22)

The original reset support commit ea71631b7129828c0da4f9d40ec172b7b2c24105
was motivated by Allwinner H6 Hantro G2 reset lines:
https://github.com/torvalds/linux/commit/ea71631b7129828c0da4f9d40ec172b7b2c24105
It is not evidence that holding all four RK3588 AV1 resets across generic PM
power-off/on is required or correct. Conversely our RK3588 results do not
justify removing reset handling globally: other SoCs must retain their path.
The upstream teardown-order patch remains a separate, attributed backport.
The new keep-reset-deasserted option is a local causal experiment, default off,
restricted by the RK3588 AV1 compatible, not an upstream patch or production fix.

### Vendor AV1 reset ownership comparison

Rockchip develop-6.1 inspected at 77168c8d5ab82399f65a80e9f807b50ba37cf483:
https://github.com/rockchip-linux/kernel/blob/77168c8d5ab82399f65a80e9f807b50ba37cf483/drivers/video/rockchip/mpp/mpp_av1dec.c
https://github.com/rockchip-linux/kernel/blob/77168c8d5ab82399f65a80e9f807b50ba37cf483/arch/arm64/boot/dts/rockchip/rk3588s.dtsi

Vendor av1dec_reset requests PMU idle, asserts the two video resets, waits 5us,
deasserts them, then leaves PMU idle. Its AV1 node declares only SRST_A_AV1 and
SRST_P_AV1. Our mainline-style AV1 node additionally declares both AV1_BIU
resets, and the Hantro array assertion holds all four across remove.
This supports investigating reset ownership/BIU lines separately, but is NOT
proof that blindly transplanting the vendor sequence into mainline is safe.
The local opt-in test omits the entire final assertion; it cannot distinguish
core-reset from BIU-reset effects. A subsequent targeted test must isolate
those lines while retaining the other SoCs' reset behavior.
