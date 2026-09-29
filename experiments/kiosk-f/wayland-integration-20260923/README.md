# Persistent Wayland integration, 2026-09-23

Audit correction: the full-f runtime already includes /usr/bin/weston 14.0.2
with DRM, libinput and GL. Only the PATH-preferred /opt/weston16 is headless.
Previous physical Chromium H264/HEVC/VP9 tests used Weston14 DRM and were
confirmed visible/fluid by the user (main10-physical-20260922/README.md).
A new Weston16 DRM build is unnecessary and was stopped.

A 40-second isolated live smoke used the new supervisor, existing Weston14,
scoped DRM/render/input/media devices, SYS_ADMIN and an independent 120-second
rollback timer. Weston enabled HDMI-A-1, rotated output, associated ILITEK event0
and event1, loaded kiosk-shell, and launched sandboxed Chromium. Timeout124 is
intentional. Cleanup restored the original X11 kiosk. No failed systemd units.
This is not a new per-codec performance or physical touch confirmation.
Missing chrome_crashpad_handler was found and added from the matching NUC build.
78 existing regression tests and 3 Wayland output/rotation tests pass. X11 remains default; Sunshine on Wayland is
rejected until that capture integration has evidence. Saved /config stays intact.

CLI generation is incremental: retain unchanged compiled binaries from the
matching source-built package, regenerate container templates and the COMPLETE
configuration caches with the original source generators/libvyosconfig, replace
changed Python helpers and repack. Never merge caches by hand. Both reftree
locations must be updated. The new offline image installs the resulting complete
package through dpkg and checks owner lookup. No release workflow/main changes.

First boot of the resulting SD image and update preservation on actual hardware
remain separate tests. The guarded setup helper now offers --display-backend
wayland, supplies discovered decoder/render/media nodes, and initially retains
software decoding; video-decode auto is an explicit subsequent choice.

## Completed image build

Both A-D/F artifacts were built on NUC. ISO contents verified against its embedded
SHA256SUMS, raw GPT verified, compressed image passed xz --test. Offline checks
confirmed display-backend owner, changed kiosk helper, Weston14 runtime metadata
and first-install helper. ISO control mount needed explicit loop-node creation
in Docker; final verification passed. No image was flashed during this step.

- img.xz SHA256: 9a0a3cda3afa6ec874044a5a05d1ca4d87ceca463f83fbb0d8cecba1690552a1
- iso SHA256: cbbab7284c3f27a14e051e60e399aaa40bc147a13221ec5d330249e8290ac4b3
- Local delivery: /mnt/entwicklung/projekte/VyOS/arm/images/rock-5b/20260923-abcd-f-wayland/
- NUC output: /home/photobooth/vyarm-board-build-20260922/wayland-image-20260923/output/
