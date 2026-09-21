# Profile F: generic hardware approach

Agreed with Frank on 2026-09-21. This records the target architecture and the
limits of current evidence; it does not enable experimental paths in releases.

## Common runtime, hardware-specific support

Keep a common profile-F runtime and CLI. Discover devices, supported formats,
encoder/decoder backends and required permissions by capabilities rather than
selecting application behavior by board name. Report the backend actually used.
Use a validated accelerated path when available and retain a working CPU fallback
when acceleration is unavailable or fails. Encoding, color conversion, browser
rendering and video decoding are separate capabilities and must be tested separately.

Kernel drivers, firmware and Device Tree remain SoC/board-specific. Builder
support for a board does not imply support for every multimedia acceleration path.
The intended packaging is a common F base with optional hardware-family support.
This is not yet a completed, universally validated implementation.

## RGA scope and Orange Pi 5 Plus

The experimental full-CSC correction is gated on RGA hardware revision 0x03263318,
not the ROCK 5B board name. It is currently proven only on our ROCK 5B. Other
revisions must not inherit the correction without validation. Even matching
revision numbers require compatible drivers, buffer formats and runtime tests.
The current Sunshine converter accelerates same-size BGR0-to-NV12 conversion;
scaling intentionally falls back to CPU. It is copy-based, not zero-copy.

Orange Pi 5 Plus uses RK3588 and is therefore a candidate for reuse of the RGA,
MPP/H.265 and decoder work. It still needs its own board image and Device Tree,
working clocks/power domains, device permissions and HDMI/output validation.
No Orange Pi live test has been performed and support is not yet certified.
Official hardware reference:
https://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/details/Orange-Pi-5-plus.html

## Patch provenance

- Decoder work: upstream Linux rkvdec code and subsequent fixes backported to
  6.18.50; exact references are in sunshine/decoder-investigation/upstream-reference.json.
- RGA color correction: locally developed patch informed by Rockchip vendor
  register code and numeric reference tests; see sunshine/rga-investigation/.
- Sunshine persistent RGA converter, counters and CPU fallback: local integration;
  see sunshine/rga-converter/.
- MPP/H.264/H.265: existing MPP and ffmpeg-rockchip foundations with our Sunshine
  integration and experimental lifecycle/ownership fixes.

## Promotion and update rules

Keep experiments on the F branch and opt-in test paths. Do not change main or
existing release workflows as a side effect. Passing standalone or live-container
tests does not substitute for a complete image build and boot/update test.

Before enabling a backend by default, verify capability detection, numeric output,
repeated use, error recovery, permissions and CPU fallback. Validate on each newly
supported hardware family/revision. Preserve user configuration across updates;
initial defaults apply to first installation or missing values, not as an
unconditional replacement of existing settings. Landscape remains the initial
orientation default. Anthias remains a separate future alternative test path.

## Potential reuse by profile D (KVM over IP)

Source audit: tools/kvm-cli/vyos-kvm-video-runner already uses ffmpeg-rockchip
h264_rkmpp or GStreamer mpph264enc on its Rockchip provider. Its GStreamer RGB
capture path selects v4l2convert/RGA for BGR3/RGB3; native NV12 bypasses conversion.
Therefore the RGA color correction is relevant, but the current F numeric proof
covers XBGR32-to-NV12, not D's packed RGB/BGR24 formats. Validate those formats,
colorimetry/range propagation and capture output before enabling it in D.

FFmpeg MPP lifecycle/ownership fixes may benefit D's FFmpeg backend if its pinned
source contains the same affected code. They do not automatically apply to the
separate GStreamer MPP plugin. H.265 is an optional future D path requiring codec
selection, transport/client compatibility and latency tests; D currently builds
its runner around H.264. Sunshine-specific converter code is not a drop-in D
component, though capability checks and tests can be reused.

The new rkvdec decoder primarily serves compressed video playback. A normal raw
HDMI capture-to-encoder KVM path does not need video decoding. No D code, default,
workflow or live configuration is changed by this audit.

## Shared RGA layouts (F and D)

NV12 and NV12M are memory layouts of the same semi-planar YUV 4:2:0 representation,
not different color spaces. Select the conversion matrix from explicitly
negotiated colorimetry/range, independently of contiguous versus separate-plane
storage. The common experimental patch chain now has an optional third patch,
`sunshine/rga-investigation/0003-experimental-rgb-layouts.patch`, for RGB24/BGR24
and NV12M. It retains the verified hardware-revision gate and existing defaults.
No board name is added. F's 32-bit reuse test and D's RGB tests have passed on
ROCK; other revisions, default/unknown metadata, scaling and rotation remain
outside that evidence. This is shared experimental support, not release activation.
