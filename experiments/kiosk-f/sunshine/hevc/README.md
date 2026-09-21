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

`probe.sh` uses disposable state and shares the kiosk network/IPC namespace
for its abstract X11 socket. Test listeners bind loopback on a separate port
family; the probe grants /dev/mpp_service and the diagnostic DRM allocator card. It accepts
success only when Sunshine reports both Found H.264 and Found HEVC encoders.
It does not copy/use existing credentials or request a live client session.

Build correction, 2026-09-21: FFmpeg HEVC compiled successfully, but the original
Sunshine step failed because `/buildcache` was an external mount in the earlier
build and is absent from the image. The candidate now explicitly configures its
own CMake build tree with the same backend/link options before compiling. This
reuses the cached FFmpeg layer, not the absent Sunshine cache.

## Live capability result, 2026-09-21 overnight

Build completed successfully. Images:
- Sunshine builder: a332c7a5036afdebe08052dd98fe741006da070af109da175abd0d1031092eeb
- Kiosk candidate: 33a15bdf6c0411cd8692420566e3781ccdd3a80ee5665a8f2eb9b107982398a7

The disposable live probe reports both `Found H.264 encoder: h264_rkmpp [rkmpp]`
and `Found HEVC encoder: hevc_rkmpp [rkmpp]`. It uses a copied X cookie and shared
network namespace to reach X11's abstract socket (initial private-network/socket
mount tests could not reach the display). Its own listeners bind exclusively
127.0.0.1 with a different port family 48989; input/audio/UPnP are disabled and
no live state is mounted. DRM card0 is required for the MPP allocator on this
host, in addition to mpp_service. This diagnostic card selection is not a generic
SBC provisioning policy. A real Moonlight HEVC stream/quality test remains open.
The running kiosk image was not replaced. CPU conversion remains in use.
Remote log: /config/kiosk-test/builds/hevc-20260921/probe6.log.
