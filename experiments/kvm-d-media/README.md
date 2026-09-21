# Profile D: additional media experiments

These are **additional explicit test options**, not replacements for profile D's
existing FFmpeg, GStreamer or uStreamer implementations. No production runner,
CLI schema, default, installed FFmpeg or normal-boot kernel is changed. Work is
kept on the F experimental branch pending separate review for profile D.

## RGA correction

Apply the shared `../kiosk-f/sunshine/rga-investigation/0003-experimental-rgb-layouts.patch` after profile F's experimental full-CSC
patch (which itself follows the test2 BT.601 correction). The additional patch
allows BGR24/RGB24 input and NV12M output on the same verified RGA revision.
Build/sign an external module against the exact running test kernel. Never load
an ABI-mismatched module or bypass signature verification.

Why NV12M: GStreamer 1.22's v4l2convert negotiates NM12/two planes even though its
caps say NV12. Restricting the correction to single-plane NV12 left BT.709 wrong.
The second candidate includes that layout. Numeric direct tests cover BT.601 and
BT.709 with full/limited output, color bars, grays and seeded random colors.
The GStreamer integration check compares its software and RGA converters on a
solid-red source with both RGB/BGR and BT.601/709.

`gstreamer-colors.py` tests the currently loaded module. For an actual bounded
HDMI capture, `test-rga-capture.sh MODULE DEVICE NEW_OUTPUT_DIR` temporarily stops
D's video service, loads the candidate and captures 120 H.264 frames through
GStreamer/RGA/MPP. It restores the installed module and previous service state,
with a separate systemd rollback timer. Kiosk remains running. The first harness
is explicitly limited to the current HDMI-RX BGR24 1080p60 test setup, not generic
hardware discovery or a new supported CLI feature.

The live test on 2026-09-21 decoded all 120 frames at 1920x1080. The GStreamer MPP
bitstream did not report color-space/range metadata in ffprobe; correct synthetic
conversion alone does not resolve that separate signaling limitation. No latency
or full end-to-end color fidelity claim follows from this short capture.

## Patched FFmpeg and H.265 alternatives

`Containerfile` builds a separate FFmpeg CLI from the exact cached F cleanup
builder, retaining the experimental EOS/ownership corrections and adding D's
existing configurable V4L2 capture-buffer patch. Both use upstream source commit
`d90e3a1c18d7929383cf88c1b3da2e2d1c966cbf`. No system binary is overwritten.

Build from repository root with an explicitly supplied `CLEANUP_BUILDER` image
ID. The validated F cache used for this experiment is
`bd1c0b9333c6cd76338b6396feb2dbb5d0f202fe4e595d7e32912d16cdb762d7`.
This depends on a retained local experimental builder, not a public distribution.

`test-capture.sh IMAGE DEVICE MODE NEW_OUTPUT_DIR` offers:

- `h264-mpp-fixed`: the patched MPP H.264 path;
- `hevc-mpp-fixed`: the patched MPP H.265 path.

Both are bounded local captures with CPU RGB-to-NV12 conversion and explicit
BT.709 limited-range signaling. They do not switch the public RTSP/WebRTC path.
The previous D video service state is restored and a separate rollback timer is
armed before any interruption. Outputs can contain actual HDMI screen contents:
keep recordings private on the test host; only technical results belong in Git.
Browser/WebRTC HEVC compatibility and long-duration performance remain separate
validation tasks. GStreamer uses its own MPP plugin and does not automatically
inherit FFmpeg lifecycle fixes.

The F converter reuse regression also passed with the extended D candidate:
960 frames across portrait/landscape and four matrix/range combinations, maximum
component error 1; see f-regression-20260921.txt. This verifies the shared
32-bit conversion path remains functional in the tested cases.

## Results and optional colorimetry propagation

The corrected FFmpeg runtime image is
`1ec163bc98c45a9c1baf29a5e53e1e442e7a76669d98650b2760ddffc3401683`.
Both codecs passed two separate actual-HDMI captures of 120 frames each, with
BT.709 limited-range signaling. `capture-results-20260921.json` records results.
Use `RUNTIME_BASE=3fac48e2a9b718d0347acfa997196486963df120546a8339c4b0017fd42b6005`
as well as the explicit cleanup builder when building Containerfile. The initial
builder-only runtime lacked the container-specific MPP device-tree path fix;
its failed run restored the existing service. The final runtime retains that fix.

The live plugin reports version1.22.9 and is not assumed byte-identical to the
Meonardo pinned source. Its binary lacks `prep:color*` keys. In the pinned source,
`gst_mpp_enc_set_format` passes dimensions/format/FPS to MPP but no colorimetry.
The separate candidate reproduces missing VUI with its new option disabled.

`0001-opt-in-gstreamer-mpp-colorimetry.patch` adds process-local
`VYARM_MPP_COLORIMETRY=1`. It maps negotiated YUV matrix, primaries and transfer
through GStreamer's ISO conversion functions and maps range enums explicitly
(GStreamer full=1/limited=2, MPP limited=1/full=2). It sends both MPP prep config
and frame metadata. No board-name or resolution-based color-space assumption.
Unknown values stay unspecified; RGB/internal conversion is not covered.
The option defaults off, so this remains an additional path.

Containerfile.gstreamer builds against Bookworm's GStreamer1.22 ABI and the live
MPP shared library in an isolated image. Header cache metadata had an irrelevant
newer-libc `-lmvec` dependency; the build removes it only from this isolated
shared-library pkg-config metadata. No host libraries are altered.

`test-plugin-colorimetry.py` selects the candidate through a private plugin
folder and registry, checks the actually loaded path, and compares option off/on.
All12 cases passed: H.264/H.265, BT.601 limited, BT.709 limited and BT.709 full.
Each encoded5 frames and verified VUI with ffprobe. The off cases reproduce
missing H.264 color fields and HEVC's implicit limited-range behavior.
See gstreamer-vui-results-20260921.json.

Combined actual HDMI -> corrected RGA/NV12M -> candidate MPP/H.264 also passed:
120 decoded1080p frames, now with BT.709 matrix/primaries/transfer and TV range.
The earlier missing-VUI limitation is thus resolved in the explicit candidate,
not in the unchanged installed plugin. Original FFmpeg/plugin checksums and D
runtime configuration were verified unchanged; D and F services are active.
This does not establish long-duration stability or browser HEVC support.

Source reference:
https://github.com/Meonardo/gst-rockchip/blob/99c594d3090ee1b4721ef0a9c1e4a99ea3de52e9/gst/rockchipmpp/gstmppenc.c
