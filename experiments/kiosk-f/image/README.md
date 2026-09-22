# Local complete ROCK 5B image candidate, 2026-09-22

Build only on feature/kiosk-profile-f. Local A/B/C/D/F selection; E is excluded.
No release workflow/default branch changes or publication. This is an experimental
installation/update pair, not a declaration of complete AV1 or display stability.

## Inputs and workflow equivalence

Follow build-board-candidate.yml: matching official ARM64 raw artifact/provenance,
board kernel + modules + DTB, firmware provider, profile package, rootfs assembly,
matching initramfs, SD image, create-system-image-iso.sh, hashes and image audit.
NUC uses native x86 cross compilation for the kernel and the existing ARM64
Chromium artifact; ARM64 rootfs commands execute via QEMU in a privileged,
isolated Docker build container. This differs from Actions' native ARM64 runner.
Do not modify host disks; loop devices must refer only to named build files.

Raw source: workflow run 35465749920, version 999.202609191955, source commit
4571978c8542a1f996af8a4913c787eecfb0b15d, kernel 6.18.50,
vyos-1x 999.0-14924-g27383e4f1. A–D userspace and firmware reuse checksum-backed
artifacts from that successful workflow. EDK2 v1.1 boot contract unchanged.

Kernel source starts from the locally validated test4 tree; merge the recorded
VP9 VDPU381 series, RCB sizing, H264 B1 comparison and HEVC SPS/RPS bounds.
Build all modules and the kernel together as 6.18.50-vyos to match the raw ABI
contract. Never reuse incompatible external .ko files or private signing keys.
A new build-local signing key signs this kernel's complete modules; never ship it.
RGA full-CSC and RGB/NV12M extensions are available behind
rockchip_rga.experimental_full_csc=1 (default off), retaining revision gating.
Do not promote the later experimental VSI identity/TLB/reset candidates here.

Runtime includes the SHA256-pinned P010/color/AV1 Chromium from the NUC,
Weston16/Mesa support, current kiosk/display/touch/Sunshine helpers and the
optional RGA Sunshine executable under /opt/vyarm/experimental/sunshine-rga.
The normal Sunshine executable remains the existing default. The standard
X11 touch kiosk remains default; the verified V4L2 browser recipe requires
Wayland and explicit device grants. Packaging Chromium does not establish that
hardware decoding is active in the normal X11 session. AV1 reset/PM and display
faults remain separate experimental limitations.

## First boot and update ownership

A versioned, checksummed container archive is embedded in the read-only rootfs.
The import service uses VyOS' persistent container storage before configuration
load. Existing matching image IDs are reused. Tag collisions stop with an error;
no retag/removal of user images, config commits or service configuration edits.
Defaults remain landscape, software graphics and remote access/audio disabled.
Activation/device selection remains an administrator decision like other profiles.

A systemd generator emits input/startup companions only for native kiosk Quadlets.
Saved URL, rotation, devices, remote settings and persistent state remain owned by
VyOS configuration and the selected /state bind mount. The generator only writes
transient units. The image does not contain lab credentials, fixed input IDs,
paired clients, browser profiles or the live router's config.boot.

Use native `add system image <ISO>` and choose to copy the current configuration.
Retain the previous image as fallback. Do not format persistence or replace the SD
card when testing an update. Existing containers continue using their configured
tag until explicitly changed to the new runtime; the old tag/state is not deleted.
A real boot/update/rollback and hardware test remain necessary after artifact
validation; offline configuration-preservation tests are not a live upgrade.

Build results, exact image IDs, checksums and final paths will be recorded with
finished artifacts. Do not describe the images as built until these exist.
