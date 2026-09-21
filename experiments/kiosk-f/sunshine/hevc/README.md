# Experimental H.265 MPP candidate

Separate images, no live kiosk replacement. Extends the retained H.264 Sunshine
builder with ffmpeg-rockchip hevc_rkmpp and an HEVC encoder entry in Sunshine's
normal codec probing. Keeps CPU-backed NV12, existing CBR policy and H.264
fallback. No board-name selection, AV1 advertisement or 10-bit/HDR format added.

Containerfile.runtime layers only the new Sunshine binary onto the accepted
CLI/touch image, retaining container-compatible MPP library and all state paths.
No customer data, pairing or passwords are copied into the image.

Live build started on ROCK under systemd unit vyarm-hevc-build; CPU quota100%,
MemoryMax2G, Nice10. Logs/context/base image ID under
/config/kiosk-test/builds/hevc-20260921. Build success does not imply hardware
codec success: still require isolated probe, real Moonlight negotiation, color,
portrait/input/audio-policy regression, and encoder latency/CPU measurements.
Keep original image and H.264 settings available for rollback. Current tags are
local experimental dependencies, not immutable release inputs; resolve digests
and publish reproducible artifacts before production workflow use.

`probe.sh` runs with a private network namespace and disposable state, sharing
only X11 access with the running kiosk and granting /dev/mpp_service. It accepts
success only when Sunshine reports both Found H.264 and Found HEVC encoders.
It does not copy/use existing credentials or request a live client session.

Build correction, 2026-09-21: FFmpeg HEVC compiled successfully, but the original
Sunshine step failed because `/buildcache` was an external mount in the earlier
build and is absent from the image. The candidate now explicitly configures its
own CMake build tree with the same backend/link options before compiling. This
reuses the cached FFmpeg layer, not the absent Sunshine cache.
