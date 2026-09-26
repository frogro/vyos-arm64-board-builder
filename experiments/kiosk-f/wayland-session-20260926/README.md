# Wayland HDMI session regression, 2026-09-26

Installed image: 999.202609191955-wayland-20260923, kernel 6.18.50-vyos.
Container f4e3afdd168d0fe60238930cb843d378a189878b2479cd8b2544ffac7b77aeec.
Chromium SHA256 d1f979a39d0402060364e5a9202cb6e8772a7e3ec90c91622151defcb851eeb6
matches the successful 20260922 candidate and delivered runtime manifest.
No evidence of a missing Chromium patch. Build integration changed session setup.

## Controlled comparisons

- Production root Weston DRM/kiosk-shell: GPU SIGSYS on aarch64 syscall119
  sched_setscheduler targeting another TID; browser falls back to software.
- Adding card1 alone: same failure. Static render group membership alone: same.
- Same container/browser with Weston headless: H264 V4L2VideoDecoder, but large
  presentation drops; establishes decoder availability, not display performance.
- Reconstructed earlier unprivileged Weston with external seatd: H264 hardware,
  3/600 dropped. Scoped devices/capability; no privileged-container option.
- Change that comparison to root Weston: same SIGSYS/fallback failure reproduced.
- Corrected production supervisor uses external root seatd for scoped device
  access and runs both Weston and Chromium as kiosk with node-derived groups.
  Chromium sandbox remains enabled. No Chromium binary or kernel changes.

Corrected supervisor, physical HDMI/90-degree rotation, short 1080p60 fixtures:

| Codec | Decoder | Frames | Dropped | End |
|---|---|---:|---:|---|
| H264 High, 8 bit | V4L2VideoDecoder | 600 | 1 | EOS |
| HEVC Main10 | V4L2VideoDecoder | 300 | 3 | EOS |
| VP9 Profile0 | V4L2VideoDecoder | 300 | 5 | EOS |
| AV1 Main, 8 bit | V4L2VideoDecoder | 300 | 2 | EOS |

CDP kIsPlatformVideoDecoder=true for all four. These are short integration
checks, not endurance, calibrated colour/HDR or fault-recovery qualification.
Monitor output was enabled; this run has no new human per-codec visual check.
81 existing kiosk tests passed. Independent systemd timers restore normal kiosk.
The exact lower-level Mesa/Wayland/credential interaction behind SIGSYS has not
been traced; correcting compositor user reproduces the known-good session.

## Packaging

The helper source is updated; runtime build checks now require seatd. The small
Containerfile here accepts that helper in its context to create a separate,
versioned correction over the delivered image. Keep the old tag for rollback.
Existing SD/ISO artifacts are unchanged and must be rebuilt with this runtime.
No release/main workflow modification. Hardware decoding additionally needs
scoped compressed decoder video nodes and their media nodes in saved VyOS config;
changing display-backend alone does not add devices to an existing installation.

## Persistent kiosk verification

Built and selected `localhost/vyarm-kiosk:wayland-user-20260926`, image ID
`3b7a84a541ae1b766062167ef3a598b20609a345df3a7b8c5fef0b73fa800fb8`.
The normal `vyos-container-kiosk.service` now starts seatd as root and Weston,
Chromium and the session as kiosk. Saved backend=wayland, rotation=90,
video-decode=auto, both capture-buffer options enabled. Removed the unsuccessful
extra card1 test mapping; scoped decoder and media mappings remain configured.

Repeated short fixtures inside this actual service container (persistent-results.json):
H264 3/600 dropped, HEVC Main10 2/300, VP9 3/300, AV1 4/300; all EOS,
V4L2VideoDecoder and platform decoder true. Restarted the service after probes:
normal configured webpage restored, no failed systemd units, no new SIGSYS.
Independent recovery timers were stopped after successful restoration.
A VAAPI initialization warning still occurs during capability probing; measured
playback uses V4L2, not VAAPI. This does not certify all website video formats.

Rollback, in VyOS configuration mode, one command per line:

```text
set container name kiosk image localhost/vyarm-kiosk:wayland-corrected-20260923
set container name kiosk kiosk video-decode software
commit
save
exit
```

The old container image and installed system image remain available. This is a
live runtime correction, not a new SD/ISO release. The next build must package a
new runtime built from the corrected source and update its runtime manifest/tag;
reusing the Sep23 runtime archive would reintroduce the defect. Existing config
must be preserved on update, with any runtime tag migration made explicit.
The first-install setup already discovers compressed decoder queues by format;
existing containers require their saved device mappings separately.
