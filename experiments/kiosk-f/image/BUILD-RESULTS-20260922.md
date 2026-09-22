# Completed local ROCK 5B A–D/F test images

Final artifact directory:
`/mnt/entwicklung/projekte/VyOS/arm/images/rock-5b/20260922-abcd-f`

- SD: `vyos-999.202609191955-rock-5b-network-tailscale-kvm-kiosk.img.xz`
  SHA256 `7366873951989633df41d6fcf9140c2e3bcb807256fe918c944ccec974c03e17`
- Update: `vyos-999.202609191955-rock-5b-network-tailscale-kvm-kiosk.iso`
  SHA256 `6c74847ff4a7dc69fb6db5ae7f4f1a4124578d2cdf966e6bf2f22d52246ab342`
- Uncompressed SD image also retained (4,311,744,512 bytes). Use >=8 GB media.
- Matching final copies remain in the NUC's `vyarm-board-build-20260922/output`.

Build code through 4934b6b; runtime content through 6d49ad3. Source pins,
CLI version and runtime/Chromium checksums are in artifact-side build-inputs.json,
cli-build.json and runtime.json. Profile E excluded. No push or release publication.

Validation passed:

- Full kernel and CLI package builds, complete signed module installation and
  eight official VyOS OOT modules; no unresolved module symbols.
- Profile/CLI unit tests and image integration tests, including preserving
  existing config/state and rejecting an occupied container tag.
- Real FFmpeg capability probes under ARM64 emulation. Fixed grep -q/pipefail
  SIGPIPE false failures without skipping encoder capability checks.
- First-boot container import ordered after native persistence growth.
- Generated initramfs, firmware/partition checks, EFI and ext4 checks, ISO internal
  hashes, xz integrity, and final SHA256 checks after copying to the development disk.
- Read-only final artifact audit: identical SD/ISO kernel, initramfs, DTB and
  squashfs; A–D/F identity; new CLI commands; checksummed Chromium runtime; eight
  signed OOT modules and 1,731 modules total; Mali firmware and rsyslog fix.

Kernel was cross-compiled natively on the NUC. ARM64 rootfs operations used QEMU.
The final rootfs and output compression used native x86 tools. A completed rootfs
was repacked solely to add the first-boot service ordering fix; kernel, CLI and
Chromium were not rebuilt for this packaging change.

Not tested: booting these final artifacts or a real live system-image update.
User configuration retention is tested offline only. Existing runtime tags/state
are not replaced automatically. Standard F remains X11; the proven V4L2 browser
recipe still requires the separate Wayland test path. AV1 reset/PM/display fault
recovery remains experimental. See artifact-side TESTHINWEISE.md.
