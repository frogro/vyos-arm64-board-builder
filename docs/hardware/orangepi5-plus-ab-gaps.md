# Orange Pi 5 Plus A/B follow-up (2026-09-29)

The live 70e1ac3 image's module presence alone did not prove RK3588 device support.

Implemented in this change:
- Materialize linux-firmware WHENCE aliases from the VyOS-pinned source, including
  Realtek Bluetooth config aliases. Resolve chains and reject escaping/cyclic links.
- Enable CPU_THERMAL, DEVFREQ_THERMAL and ENERGY_MODEL for Orange Pi; Panthor's
  disabled cooling stub caused the warning despite successful GPU initialization.
- Select the visible ConfigFS function switches. Require both selectors and actual
  HID/storage/ECM/NCM/RNDIS/UVC/UAC2 function symbols after olddefconfig.

Validation: matching local 6.18.50 olddefconfig retains all three thermal settings
and produces all seven function modules. Firmware alias/closure tests and existing
extended-network/provider tests pass. This is not a full image or hardware test.

Still required before claiming complete peripheral support:
- DP0 via VP2, PHY0/FUSB302 graph/Altmode and DP audio, adapted to this kernel's
  bindings. Do not copy vendor endpoints verbatim or enable unconnected DP1.
- RK3588 VDPU381 decoder backport (current rockchip_vdec only matches RK3399).
  The ROCK experimental source/patch includes HEVC UAPI and fixes, not just a
  config change; audit against the final working ROCK kernel before porting.
  Vendor MPP RKVDEC2 is an alternative API, not a concurrent owner of the same core.
- CSI capture (DPHY/CSI/VICAP), ISP and sensor-specific graph. Upstream rkisp2 RFC
  adds about 15k lines and requires separate VICAP series plus userspace support:
  https://lists.infradead.org/pipermail/linux-arm-kernel/2026-April/1123416.html
  This is missing integration, not merely untested. Native HDMI RX is independent.

Reference comparison: Armbian build 6125ad65a2996a5dc8c1fc48ec5fe58ac4706b59,
Orange Pi build a95129bf30ea11886cc35f08ebb3e69695a26656, vendor DT source
f6eedab0cbe9b4be3f855661a0a7e7008812d40a. Configs/DTs are reference evidence;
no reference binary image was booted or exhaustively audited.

Do not launch or label the next build as closing DP/decoder/CSI gaps on the basis
of this change alone. SD/eMMC and update ISO must use the same verified payload.

## Follow-up backport preparation

The DP video and RK3588 decoder source changes are now board-scoped in
profiles/base-hardware/kernel-patches/orangepi5-plus. Experimental CSI/VICAP/ISP2
modules and disabled DT blocks are also included after cross-compilation.
Their detailed provenance, validation and remaining limitations are in that
folder's README. This supersedes the earlier missing-driver inventory above;
it does not establish a complete tested camera pipeline or DP audio support.
Full kernel/image and live hardware validation still follow.

## DP audio follow-up

0004 now supplies the audio driver port, internal SPDIF2/DP0 sound card and
SPDIF module requirement. Source and DT/object compile checks passed; hardware
acceptance and complete image build remain pending. The earlier statement that
DP audio has no implementation is superseded by this backport. Retain the
previous bootable image until USB-C video/audio and hotplug tests pass.
