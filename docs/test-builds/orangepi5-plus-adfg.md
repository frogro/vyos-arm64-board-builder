# Orange Pi 5 Plus A–D/F/G integration candidate

- Base: `main` at `f3e3ed0` (includes board-scoped DP video/audio,
  RK3588 decoder and experimental CSI/ISP backports, firmware aliases,
  thermal and ConfigFS corrections, EDK2 and logging/firstboot fixes).
- Imported integration: `test/profile-g-steamlink-integration-20260929`
  at `e6e3add`; no merge into main.
- Branch: `test/orangepi5-plus-adfg`.
- Boot/update: Orange Pi EDK2 v1.1, `efi-firmware-dtb`.
- Output: a shared SD/eMMC rootfs and system-image update ISO. Image size is
  16 GiB plus layout slack: use at least 32 GB media for initial installation.

## Included

B board drivers/firmware from main; C Tailscale; D HDMI/V4L2 capture,
MPP encoder/media stack, cached CPU conversion and bounded fallback; F
Chromium/Sunshine including direct GPU/RGA and portrait/input fixes; G
Miracast, UxPlay/AirPlay, Moonlight and Steam Link including private Request
HEVC decoder fixes and native CLI.

Both offline runtime containers are rebuilt from checksummed userspace
inputs plus this commit. No ROCK kernel, DTB, EDK2 binary, saved configuration,
credentials or device identities are imported. The CLI is rebuilt against the
vyos-1x version actually present in the selected raw image.

Orange Pi has its own D provider overlay enabling the shared VEPU580 cluster.
USB-C remains OTG; the other controller remains host. Gadget readiness is
checked at runtime. No ROCK Type-A peripheral override is applied.

## Validation and acceptance

Build checks cover profile selection, native CLI, firmware/kernel requirements,
main boot/update regressions, G receiver tests, and the actual compiled Orange
Pi DTB overlay. CI additionally checks rebuilt container loadability, decoder
libraries, CLI files and exact F/G commit provenance in the assembled rootfs.
The ISO packages that same rootfs. These are build checks, not Orange Pi
hardware acceptance. CSI sensors do not imply a working RK3588 CSI/ISP stack.

Live acceptance remains necessary for GPU/codec/audio, HDMI RX, USB-C HID,
C persistence and F/G receiver transitions. Existing ROCK test results are
reference evidence only. No live update or reboot is part of build dispatch.

Fallback: keep the existing A/B boot image and configuration backup. Before
later ISO installation, verify its checksum, Orange Pi board identity and
`efi-firmware-dtb` compatibility, and retain the previous bootable image.

## Dispatch

Use `build-board-candidate.yml` on this branch, with board `orangepi5-plus`,
`extended_network`, `tailscale_subnet_router`, `kvm_over_ip`, `kiosk_f`,
`receiver_g` enabled; expected provider `efi-firmware-dtb`; publication off.
