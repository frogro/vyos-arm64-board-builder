# Chromium hardware decode proof — 2026-09-21

**PASS for the supplied H.264 and HEVC Main 8-bit 720p fixtures in an isolated
Wayland container. Production X11 kiosk is unchanged.**

- ROCK5B, kernel 6.18.50-vyos-f-test3, /dev/video2 rkvdec + /dev/media0.
- Existing Debian Chromium 153.0.8010.47-2~deb13u1, unmodified binary.
- Weston 14.0.2 headless backend + GL renderer, no physical output takeover.
- GPU: ANGLE/Mesa 25.0.7, Mali-G610/Panfrost.
- Browser sandbox retained, non-root kiosk user, isolated profile, no network
  except in-container loopback HTTP fixture server and debugging pipe (no port).
- Both clips end, each 90 total frames over 3 seconds. Final HTTP test drops:
  H.264 2, HEVC 1. Short synthetic functional test, NOT a performance benchmark.
- Both Media diagnostics report V4L2VideoDecoder and kIsPlatformVideoDecoder=true.
- Final canvas frame89 compared with FFmpeg-decoded last frame; per-channel mean
  absolute RGB differences: H264 [0.809,0.583,0.491], HEVC [0.807,0.584,0.488].
  These RGB paths are not byte-identical, unlike the earlier raw I420 tests.
  PNGs included; HEVC image visually inspected, matching test pattern/frame89.
- Existing F/D services active after tests; no test container left running.

## Necessary runtime setup in this experiment

`--ozone-platform=wayland --use-gl=angle --use-angle=gles`
plus `--enable-features=AcceleratedVideoDecoder,AcceleratedVideoDecodeLinuxGL,PreferV4L2VideoAcceleration`.
The experimental probe also uses --ignore-gpu-blocklist. Before production
integration, test whether that override is necessary; do not make it a blanket
default. Full actual flags and GPU/Media data are in the JSON results.

The source audit at Chromium tag153.0.8010.47 identified AcceleratedVideoDecoder
and PreferV4L2VideoAcceleration as separate runtime gates. Merely enabling the
GPU or exposing devices did not select the correct backend in the initial runs.
With X11-backed llvmpipe, V4L2 was reached but NV12 import/LibYUV processing failed:
H264 fell back to FFmpegVideoDecoder, HEVC failed. The isolated Wayland/Mali test
resolved this output-path obstacle. This does not prove X11 cannot work; the
production X11/Mali path still needs a separate comparison.

Headless default disables GPU: see upstream documentation
https://chromium.googlesource.com/chromium/src/+/HEAD/docs/gpu/using-gpu-hardware-in-headless-chrome.md
Exact source gates:
https://chromium.googlesource.com/chromium/src/+/153.0.8010.47/media/base/media_switches.cc
https://chromium.googlesource.com/chromium/src/+/153.0.8010.47/media/mojo/services/gpu_mojo_media_client_linux.cc

## SPS/RPS scope

FFmpeg trace_headers reports num_short_term_ref_pic_sets=0 for this HEVC fixture.
The experimental Chromium SPS/RPS patch is NOT installed and is NOT validated
by this success. Next coverage must include HEVC streams with SPS short/long-term
reference lists, then test any required patch against those streams. Do not
claim all H265 profiles or streams work from this fixture.

## Reproduction

Build Containerfile.browser-wayland on ROCK, then run test-browser-wayland.sh
with the image, fixture directory, a new result directory, decoder video node
and matching media node. This starts a private Weston compositor per codec.
No production display socket, Xauthority or running kiosk profile is required.
The finalFramePNG data URL is extracted to *.png here and removed from stored
JSON to avoid duplication. FFmpeg reference images use select=eq(n\,89).

Test image ID: d0021d3239bcd8ba5118c11bb312f236de3f8d9ab8acb834e59ed399aae11b5b.
