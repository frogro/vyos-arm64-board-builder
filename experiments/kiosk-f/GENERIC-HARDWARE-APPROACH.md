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
