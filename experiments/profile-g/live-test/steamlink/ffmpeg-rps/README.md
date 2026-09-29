# Isolated FFmpeg 7.1 HEVC RPS experiment, 2026-09-29

Backport candidate from Detlev Casanova's Collabora FFmpeg branch, commit
`a8eb4b006d055f0be43d4a03d87472d2f199f177` (source.json).
The earlier 7.1 WIP commit was inspected but not used: it lacked LT controls
and did not preserve the raw/reordered RPS flags separately.

Base remains jernejsk FFmpeg `904a85173fab816bb3c30652300efa93f2333657`.
Apply `0002-exact-7.1-backport.patch` to a separate source copy with `patch -p1`.
It applies without fuzz or offsets to the pinned source. Do not apply both
patches: 0001 preserves the original upstream diff for attribution/review.
The exact backport keeps the 7.1 start_frame ABI and includes the guarded
`v4l2-hevc-rps-compat.h` after `v4l2_request.h`. Its definitions are
from Linux UAPI v4l2-controls.h; runtime probes must confirm both ST/LT
controls. No host kernel headers or system libraries are replaced.

Build and install under a separate DESTDIR. The candidate libavcodec61 hash
is `14519fd64c75711306d57e11a83af0f0be9641ae02d3449f233126fb5c9c08ce`.
libavutil59 remains `0b0eecb17fbaf87b79c94dfafe590d11b90d2342e7af0ed70d37f5b148dce280`.
Use a separate exact-hash preflight for the candidate, retaining the original
preflight and original libraries for rollback. This directory is NOT yet
wired into image builds or selected by the native CLI.

`compare-decode.c input.hevc hardware(0/1) max_frames` decodes to ordered
I420 frame MD5s. HW mode explicitly requests V4L2REQUEST and DRM_PRIME,
transfers frames to CPU only for verification, then hashes unpadded visible
pixels. Test-only transfer is not part of the Steam display path.
The captured Steam stream is local diagnostic data, not committed here.

## Pixel comparisons

360 frames from the actual Legion HEVC Steam stream: original software,
original hardware, patched software and patched hardware all match exactly.
This ordinary stream did not expose the missing RPS controls visually.

Two FATE conformance streams reused from profile F expose the gap:

| Fixture | Original HW matches | Patched HW matches | Patched SW matches |
| --- | ---: | ---: | ---: |
| RPS_A_docomo_4.bit | 4/44 | 44/44 | 44/44 |
| LTRPSPS_A_Qualcomm_1.bit | 32/500 | 500/500 | 500/500 |

All runs decoded the complete expected frame count. Reference is original
software decode. Source URLs and SHA256s are recorded under
`experiments/kiosk-f/sunshine/decoder-investigation/rps-conformance-test3/`.
Third-party streams
are not redistributed. results.json stores comparison counts.

Live patched Steam shows EXT_SPS_RPS=1 and rkvdec/S265; kernel RPS warnings
ceased in the bounded candidate run. No kernel replacement/reboot required.

Final motion run:235.386s /14120 decoded frames =59.9866fps;5s buckets
59.50–60.13fps; no video queue overflows. See ../long-motion-20260929.json.
H264 regression: all360 captured Steam frames match original software
reference in original HW, patched SW and patched HW (h264-regression.json).
Kiosk restored after testing; no image/CLI/default library change.
