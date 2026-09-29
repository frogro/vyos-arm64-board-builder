# HEVC Main10: decode succeeds, Chromium output format missing

2026-09-21, ROCK 5B, kernel 6.18.50-vyos-f-test3. Isolated containers only;
production D/F unchanged. Chromium 153.0.8010.47, Mesa 25.0.7, normal sandbox.

## Evidence

Synthetic 1920x1080 60 fps, 5 seconds / 300 frames, HEVC Main10, 4:2:0 10-bit,
BT.709 limited SDR. This is NOT an HDR or arbitrary-stream conformance test.
Two explicit GStreamer v4l2slh265dec runs reach EOS with 300 frames, native
NV12_10LE40 (DRM NV15). CPU FFmpeg reference converted by a pure packing helper
to NV15 matches SHA256 of EVERY hardware-decoded frame (300/300).
Six independently unpacked first/last samples also have zero sample error.

An initial comparison after GStreamer videoconvert to I420_10LE had different
hashes. On its first output frame, differences are at most one 10-bit LSB;
this does not indicate a decoder error. The all-frame bitexact result uses the
native packed hardware output and avoids that conversion. No claim that all
videoconvert frames have the same error bound.

Two ordinary browser runs and one verbose diagnostic select V4L2VideoDecoder
but fail SetupOutputFormat with kNoDecoderOutputFormatCandidates (status 5),
before CAPTURE allocation. The browser harness later reports a timeout/pause
abort; that is a consequence, not the root cause. Chromium's format mapping
lacks NV15. NV15 and P010 have DIFFERENT packing and cannot be aliased.

An EGL capability query in the SAME weston16-test3 browser image reports NV15
among 52 import formats. This proves format advertisement only, not successful
DMA-BUF import, rendering, color management, or HDR.

## Candidate upstream implementation

https://github.com/sky-rk3588/rk3588-chromium-nv15
Pinned source and SHA256 values: upstream-provenance.json. Upstream Chromium
CL 8094022 and ANGLE CL 8091989. The series adds NV15 end-to-end and an EGL
capability gate; upstream reports Chromium 150 / RK3588 VP9 Profile 2 tests.
That is not a validation of our Chromium 153 HEVC configuration.

Applied only to disposable copies of touched source files: ANGLE and gate
patches apply; the main patch has one rejected context hunk in
media/base/format_utils.cc. Chromium 153 added P210/P410 after P010, so insert
NV15 mapping without removing those branches. Full compile and runtime checks
remain outstanding. Series is NOT enabled in a build or deployed. Also review
whether the EGL gate correctly covers the selected GL/Vulkan backend.

Next: port with original authorship/license preserved; compile on a sufficiently
sized builder; run actual DMA-BUF import and Main10 browser tests, then compare
8-bit regressions, color ranges, seek, resolution switches and fallback.
Keep capability-based selection, never a board-name-only switch. VP9/AV1 need
separate decoder support; these HEVC results do not prove those codecs.

## Reproduction helpers

pack-nv15.c accepts raw 1920x1080 I420_10LE on stdin and emits packed NV15.
Run on a little-endian host. Compile with cc -O2 -Wall -Wextra -Werror. Pipe FFmpeg software-decoded fixture
frames through it, then python3 hash-packed.py hardware-frame-hashes.json.
The helper is deliberately fixed to this fixture's geometry, not production code.
Source fixture metadata is in source.json. Raw fixtures and diagnostic runs remain
outside Git under tmp/chromium-codec-probe/main10 and on the ROCK under
/config/kiosk-test/kernel-test3/capture-count/main10-*.

chromium153-rejected-hunk-followup.patch supplies only the rejected mapping hunk
after the pinned upstream series is partially applied. It preserves P210/P410.
This context adaptation is uncompiled; it is not a standalone NV15 implementation.

## Continued build after 21:00 authorization

The pinned three-patch series is now applied to the full isolated Chromium 153
source, alongside the disabled-by-default capture-reserve candidate and lifetime
instrumentation. Original touched files were backed up before application.
upstream-patch-port.diff adapts the upstream patch itself to preserve P210/P410;
all three adapted inputs passed dry application before their respective application.
The earlier rejected-hunk-followup.patch is an ALTERNATIVE for the scratch tree,
not an additional fourth patch when using upstream-patch-port.diff.

Full chrome + chrome_sandbox build launched via build-isolated.sh with native
GN/Ninja orchestration and ARM64 Clang under QEMU; one compile job, 3 GiB RAM,
4 GiB RAM+swap, 2 CPU quota. The script records exit status and only prints the
completion marker after both targets succeed. This does not install a browser.
No object/binary or actual NV15 browser playback proof yet.
