# Profile F build audit — 2026-09-20

Audit of conversation requirements, tracked experiment sources and live ROCK
kernel 6.18.50-vyos. This is a release checklist, not an implemented build gate.
Profile F is not yet wired into the normal image workflow. Local commits in
feature/kiosk-profile-f do not by themselves enter a GitHub Actions build.

## Generic architecture

Reuse Sunshine's actual encoder probing and software fallback. Runtime selection
must not use a board-name table. Build-time hardware providers still need the
correct kernel/DT/firmware, userspace libraries and scoped container devices for
each SoC. A driver or advertised codec alone does not prove usable encoding.
Test local display, browser rendering, capture, conversion and encode separately.
Do not assume every SBC has a hardware video encoder or exposes one through a
Sunshine-compatible backend. Software fallback must be reported, with measured
performance rather than a promise of the same resolution/FPS on every board.

## Saved work and missing dependencies

| Item | Verified status | Required before delivery |
| --- | --- | --- |
| CPU governors | 03d71e6: performance/ondemand/schedutil in base; present live | Preserve existing default |
| RK3588 MPP | Existing profile-D provider enables MPP_SERVICE/RKVENC2; present live | Reuse shared media dependencies for F without requiring HDMI capture/gadget features |
| Sunshine MPP and scoped devices | a15630a experiment committed; real H.264 stream tested | Package through F provider; currently not in release workflow |
| evdev, USB HID, virtual console, Rockchip DRM | Present in live kernel | Validate resolved final config and included modules for each selected board |
| INPUT_UINPUT | Disabled live; no F requirement wired into builder | Add and validate for native virtual-input support; retain scoped device permissions |
| HID_MULTITOUCH | Disabled live; no F requirement wired into builder | Add for broader touchscreen support; current working screen does not validate other hardware |
| Panthor/Panfrost rendering | Both disabled live; no F integration found | Select matching GPU driver, dependencies, DT/firmware and container Mesa; validate renderer and device access on each board |
| Rockchip RGA | VIDEO_ROCKCHIP_RGA=m live; synthetic conversion runs | Color validation FAILED; no tested fix committed. Keep swscale fallback |
| Pi display | VC4/V3D assertions already present in Pi validation | These do not prove Sunshine hardware encoding; test independently |
| Boot address readiness | 9a06ab2 and 77fbe03 contain helper/staged installer | Package helper/drop-in for image updates, not only live installation |
| USB discovery/rotation | Generic discovery and mapping committed, physical portrait touch tested | Hotplug/ACL reconciliation and other devices still pending |

No new kernel fix was invented or enabled during this audit. Missing symbols
require configuration integration, Kconfig dependency resolution and a final
kernel.config/module check. A source fragment alone is not proof of inclusion.
The FM350 configuration is explicitly out of scope and remains unchanged.

## H.265: deferred, not implemented

The user requested H.265 evaluation; it must not be forgotten in the next
Sunshine container iteration. Two independent blockers exist in tracked sources:

- Containerfile.build enables h264_rkmpp but NOT hevc_rkmpp. libx265 and
  hevc_vaapi are not substitutes for Rockchip hardware HEVC encoding.
- 0001-add-rkmpp-encoder.patch leaves HEVC empty and sets H264_ONLY.

Next: build a separate candidate containing hevc_rkmpp and an appropriately
validated Sunshine HEVC backend. Start with SDR 8-bit 4:2:0; do not advertise
HDR/10-bit/AV1 without testing. Keep the working H.264 image and paired identity.
Test actual Moonlight negotiation, encoder log, ThinkPad hardware decoding,
portrait capture, color correctness, input, CPU load and frame timing at the same
resolution/FPS and initially the same bitrate. Only then compare lower bitrate.
H.265 is not automatically faster or lower latency. A router kernel rebuild is
not presumed necessary: first test the existing MPP driver with new userspace.
The current vyos-1x CLI package build does not contain this codec change.

## Remaining release acceptance

- Native CLI package and help/completion; unchanged behavior of other containers.
- Limited Sunshine CLI, authoritative CLI keys and preserved web-only settings.
- Reproducible first-install defaults, no lab addresses/USB IDs/credentials.
- Image update, pairing/certificate preservation, migration and rollback tests.
- Final web-certificate provisioning and access policy; no automatic WAN opening.
- Second display and generic hotplug testing; multiple independent URLs remain
  a separate extension, not an already implemented feature.

See DEFAULTS-AND-UPDATES.md, CLI.md and live-check-20260920.md for detail.

## Required F rootfs staging: host fixes (Sep21)

Before F initramfs generation run `host/install.py` as documented in
`host/README.md`. This installs the rsyslog runtime-config start condition;
select `--panthor-arch10-8` for a matching Mali GPU to include pinned, verified
firmware plus licence and initramfs hook. Repeat in both first-install and update
rootfs builds; do not rely on live overlay files migrating into a new image.
Normal release workflows remain untouched; this is an explicit experimental F
staging step until F image assembly is wired in.

## Integration and hardware follow-up (Sep21)

BUILD-INTEGRATION.md supersedes the earlier statement that no image-assembly
opt-in exists: KIOSK_F=yes now stages the CLI/host corrections. Full image and
release workflow acceptance remain pending; CI checks are separate.
Isolated EGL test proves Mali-G610 rendering with Mesa25.0.7; live Chromium
acceleration remains unconfigured. RGA test2 improves BT.601 samples to maxerror1,
but BT.709 remains16 and range requests ignored. H.265 candidate is being built
separately, no live replacement. Browser decoding remains a separate gap:
current test2 disables ROCKCHIP_MPP_RKVDEC2 and VIDEO_ROCKCHIP_VDEC. Enabling an
encoder or passing EGL does not establish video decode; evaluate decoder driver,
matching DT nodes and browser/userspace support before next kernel candidate.

## Decoder and graphics follow-up, 2026-09-21 overnight

GPU startup and deliberate failure recovery were live-validated (aae9bbf).
Added source CLI graphics software|auto with completion/help and validation;
56 kiosk tests pass. The new leaf is not yet installed on the live router.
Local Docker package build still needs the user's offered local sudo session.

Decoder audit: test2 source exposes ROCKCHIP_MPP_RKVDEC2 (VDPU381 H264/HEVC/VP9)
under the vendor MPP driver, disabled by default; optional DEVFREQ is separate.
The examined rk3588*.dtsi files contain RKVDEC power-domain/QoS references but
no rkvdec decoder node. Those power references alone do not instantiate a decoder.
Enabling Kconfig alone is not a complete solution: inspect the final compiled
DTB and any custom overlay first, then arrange matching MPP decoder bindings and
userspace. No decoder kernel change or browser hardware-decode success claimed.
