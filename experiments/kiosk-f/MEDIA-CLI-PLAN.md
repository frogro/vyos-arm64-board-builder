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
