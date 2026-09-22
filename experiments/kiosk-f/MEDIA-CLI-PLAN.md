# Conditional media CLI plan — D and F

Requested 2026-09-21: separate autonomous tests until16:00 Europe/Berlin;
physical display test later. This is a proposal, not installed CLI syntax.
Promote options only after corresponding end-to-end tests pass.

## Preserve existing configuration

F currently owns remote access/input/audio and selected security keys; encoder,
capture and other Sunshine Web settings are unmanaged. New keys must not silently
claim existing Web configuration on update. Absent new keys retain existing
behavior. Explicit CLI selection transfers ownership of that setting only,
with a migration backup and status explanation. Reboot/update preserves explicit
values. Image capability version must match CLI/supervisor; reject unsupported
explicit options at commit rather than silently discard them.
D retains ustreamer/gstreamer/ffmpeg paths and existing defaults. Experimental
candidate runtime selection is separate and reversible, not replacement.

## Candidate configuration concepts (names provisional)

F:
- kiosk video-decode software|auto (distinct from existing graphics rendering).
  auto probes usable decoder inside the container/browser; software fallback
  reported. Do not advertise hardware success from chrome://gpu alone.
- kiosk remote codec h264|auto: auto advertises only validated encoder codecs;
  Moonlight chooses the actual negotiated codec. H265-only is not needed yet.
- kiosk remote conversion software|auto: validated RGA path preferred only for
  supported format, matrix, range and dimensions, otherwise CPU. Keep backend
  forcing out of ordinary configuration until a useful support case exists.
- Encoder backend selection normally remains Sunshine's own capability probe.
  Report chosen backend, not a board-name-derived assumption.

D:
- video codec h264|h265 as an explicit later option. H265 captures passed but
  MediaMTX/WebRTC/MoQ/browser delivery has NOT been validated end-to-end. Keep
  H264 as current default; reject known incompatible transport combinations.
- video conversion software|auto with the same capability/format checks.
- Keep codec, pipeline backend and hardware encoder as distinct concepts.
  Generic auto selection may map to MPP/VAAPI/etc only when runtime provides it.
- Correct color metadata should be automatic internal behavior. Matrix/range
  overrides belong to diagnostics only if source metadata is missing/wrong.
  Do not expose NV12 vs NV12M as customer choices: memory layout negotiation is
  an implementation concern, independent of BT601/BT709/full/limited.

## Status and diagnostics first

Extend current D/F status rather than add speculative tuning switches:
requested/effective rendering, video decoder, encoder, negotiated codec,
conversion backend, color matrix/range, fallback reason, last probe result,
runtime version and usable device identities. Separate unavailable capability
from a runtime failure. Enumerate hardware by driver/capability and stable
identity; /dev/videoN is not persistent configuration.

Document restart scope: remote settings restart Sunshine/stream only when
possible, browser settings restart browser, D pipeline changes restart D video.
Include help and completion for actual accepted choices.

## Acceptance before implementation/promotion

F standalone H264/HEVC references and repeated starts, then actual Chromium
per-video decoder diagnostics plus correct frames; controlled failures must
fall back. RGA tests already pass for gated revision, but do not imply all SBCs.
D candidate H264/HEVC/RGA recordings and VUI passed; transport/client tests and
fallback remain. Both profiles require configuration ownership, migration,
update/reboot retention and old-path regression tests. No default change or
release-workflow modification is authorized by this planning document.

## Reserved future F option (user decision,2026-09-21)

Browser-based remote viewing via WebRTC/H264 is reserved as an additional
profileF option for later. It is not part of current implementation/tests and
does not replace Sunshine/Moonlight. ProfileD already has the MediaMTX/WebRTC
H264 path; distinguish that from this future F feature in user communication.

## Browser evidence update, 2026-09-21 test3

Unmodified Debian Chromium153 now decodes the tested H264 and HEVC Main8bit
fixtures with V4L2VideoDecoder/platform=true using an isolated Weston/Mali
container. Correct final image checked against FFmpeg; production X11 kiosk
not migrated. An X11/llvmpipe comparison failed NV12 import, so device access,
graphics backend and decoder support must be reported independently.

The tested software path supports H264 but rejects this HEVC stream. Thus
`auto` must not promise software fallback for every codec: report unsupported
codec if no usable decoder remains. Do not infer HEVC capability merely from
MPP encoding or a successful H264 probe. SPS-RPS stream coverage, long-playback
performance and physical display integration remain separate acceptance items.
The earlier Chromium SPS/RPS patch prototype is not installed and was not
required for the tested stream; do not ship it as a proven prerequisite.

1080p60 tests: raw V4L2 decoder throughput has ample headroom, but browser
headless dropped-frame counters and NV12 BT709 import correctness remain open.
No automatic browser-hardware default promotion yet. Accurate status must
distinguish codec hardware selection from verified display/color behavior.

Hardware-enabled WebRTC follow-up: isolated MediaMTX→ROCK Chromium receiver now
negotiates/decodes H264 High and HEVC Main at1080p60. Thus D HEVC transport is a
viable optional test path for validated receivers, not blanket browser support.
Keep H264 default; readiness must include receiver capability, actual frames and
presentation/color validation. This does not implement the reserved F WebRTC UI.

## Agreed next step: generic browser decoder CLI (2026-09-22)

User requests recording this follow-up, not implementing it before the unified
Chromium candidate passes browser tests. Extend the existing CLI generically
across supported SBCs; no ROCK-specific forced startup flags or board-name
assumption of decoder capability. Syntax remains provisional.

- Proposed modes: auto, software, hardware-required. Auto is the intended
  default for the new design; preserve existing configurations during migration.
  Auto permits software fallback only where that codec/profile actually has a
  usable software decoder. Otherwise report unsupported playback explicitly.
- Probe driver/API capabilities, decoder/media/render devices and container
  permissions before applying an explicit hardware selection. Reject known
  unsupported requests without replacing the working configuration.
- Startup checks cannot guarantee every video's codec profile, bit depth,
  dimensions or GPU import path. Handle per-stream failures at runtime; strict
  hardware-required must report failure rather than silently use software.
  Verify that the browser implementation can enforce this mode before exposing it.
- Keep the opt-in H264 capture-buffer reserve as a separate expert option,
  gated to the supported stateless V4L2/MMAP/non-low-delay path. NV15 format
  support and HEVC SPS/RPS capability negotiation are internal features, not
  compulsory user-facing switches. AV1 support remains subject to driver tests.
- Status/help/completion: requested mode versus actual per-video decoder,
  codec/profile/bit depth when available, hardware/software use and fallback
  reason. Distinguish decoder support from GPU rendering and physical output.
- Acceptance: supported and unsupported hardware, absent devices/permissions,
  unsupported video profiles, rollback, restart scope and update/reboot retention.
  Package only after end-to-end tests; do not alter existing release workflows.

Scope: profile F local browser playback. Profile D's ROCK-side capture,
conversion and encoder selection remain separate. No requirement for customers
of D to install our patched Chromium on their receiving computer.


### Validated browser candidate update, 2026-09-22 afternoon

The final NUC binary has two independent opt-in features:
`V4L2ExtraCaptureBuffers` (H264) and `V4L2ExtraAV1CaptureBuffers` (AV1).
Each defaults to two extra request/MMAP capture buffers, clamps 0..8 and
respects VIDEO_MAX_FRAME. They remain disabled by default. No buffer reserve
change for HEVC/VP9. Report actual decoder backend and active reserve separately
from requested policy; device presence or a CLI flag alone is not proof.

Live WebRTC tests exposed missing low_delay propagation in VideoDecoderPipeline.
The final candidate forwards it for V4L2 only. Both feature-off/on now allocate
six capture buffers in the tested H264 WebRTC path, preserving the low-delay
exception. Generic CLI must not force the kiosk reserve into D's receiver path.
D's ROCK encoder and the remote user's browser remain separate capabilities.

HID USB-C–USB-A follow-up: default endpoint succeeds at high-speed. Keep the
no_out_endpoint workaround experimental/opt-in, not a board-wide default.
The configured dedicated UDC may be absent when its live DT mode is host;
report that mismatch explicitly rather than silently selecting another port.

Evidence: chromium-nuc-live-20260922 and hid-usba-20260922. No production CLI
changes implemented by this validation step.


### Additional color/P010 evidence (2026-09-22 afternoon)

P010 single-buffer plane geometry is an internal format-support correction,
not a user-facing codec switch. AV1 10-bit passes after this addition.
NativePixmapAccurateYuvMatrix is a separate disabled-by-default experiment:
BT709 EGL import instead of legacy REC601. HEVC/VP9/AV1 canvas comparisons
improve, BT601 preservation and full-range BT709 are checked with explicit
metadata. Do not enable on all boards/backends before direct-overlay and
physical display validation. CLI should expose a supported policy, not assume
that every receiver or graphics backend has the same overlay constraints.
Incomplete stream color metadata remains independent of the import correction.

### AV1 reset lifecycle gate (2026-09-22)

Codec/format support and successful decoding do not prove safe reset, module
removal, timeout recovery or system suspend. Keep lifecycle readiness separate
from requested hardware-decode policy. The powered-core-pulse experiment passes
14 removals on RK3588, but stays diagnostic/default-off until PMU-idle ownership,
error paths and real decoder-timeout recovery are settled. Prefer a driver
variant capability/callback; do not expose raw reset masks as a normal CLI knob.
Other SoCs retain their established driver behavior. See
av1-reset-research-20260922/README.md.
