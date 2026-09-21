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

## Bitstream smoke test, 2026-09-21

`encode-smoke.c` uses the same static FFmpeg encoder libraries and CPU NV12 input.
Build in the pinned builder above with:

```
export PKG_CONFIG_PATH=/opt/ffmpeg/lib/pkgconfig:/opt/mpp/lib/pkgconfig
cc -Wall -Wextra -O2 encode-smoke.c -o encode-smoke $(pkg-config --cflags --libs --static libavcodec libavutil)
```

Run the binary in the v3 runtime bundle (8b48c818...), granting mpp_service and
card0 plus the read-only compatible file at /run/mpp/compatible as in probe.sh.
Use a separate writable output directory and network=none, no live kiosk state.
The unmodified builder MPP library cannot identify the SoC inside the container;
the runtime includes the compatible-path fix and environment setting.

```
./encode-smoke h264_rkmpp test.h264
./encode-smoke hevc_rkmpp test.hevc
python3 verify-smoke.py test.h264 test.hevc
```

Both encoders emitted 120 packets for 120 moving gray-bar frames (1920x1080,
60 fps metadata, 8 Mbps requested CBR). Independent host FFmpeg decoded all 120
frames without errors. Metadata identifies limited-range BT.709. First/last
frame luma samples away from edges and all neutral chroma bytes match the
reference exactly. Results and stream hashes are in encode-smoke-results-20260921.json;
raw files remain under /config/kiosk-test/builds/encode-smoke-20260921 on ROCK.
This simple content is not a bitrate/quality comparison, speed measurement,
RGA color test, browser hardware decode or real Moonlight-session validation.

Both processes exited successfully but emitted MPP teardown warnings:
`mpp_mem_pool_put invalid mem pool ptr ... caller mpp_frame_deinit` and
`mpp_buffer_service_deinit cleaning misc group`. Treat cleanup/repeated-session
stability as open; successful bitstreams do not establish clean teardown.
The test did not replace or restart the live kiosk container.

### Teardown localization

A diagnostic-only rebuild of rkmppenc.o added stage logging (script
trace-teardown-build.sh runs inside the disposable pinned builder with /probe
bound to the smoke output directory). The traced binary ran in the same v3
runtime, without modifying any deployed image or source layer. 120 HEVC packets
were again produced. Two invalid-frame-pool warnings occur **inside mpp_destroy**,
then two more in FFmpeg's clear_frame_list, after reset has returned.
See teardown-trace-20260921.log. Therefore simply moving FFmpeg list cleanup
before mpp_destroy is not an established fix.

Pinned MPP mpp_mem_pool_put marks a returned node's check field NULL; warnings
with check=NULL are consistent with a second release of the same pool node.
MPP's packet-list destructor also deinitializes KEY_INPUT_FRAME; encoder task
cleanup and FFmpeg each have frame cleanup paths. Exact ownership/EOS/queue
interaction remains to be traced before changing lifetime management. This is
not evidence of a kernel encoder or RGA fault. No warning suppression or unproven
cleanup-order patch has been put into the runtime.
