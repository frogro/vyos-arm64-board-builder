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
