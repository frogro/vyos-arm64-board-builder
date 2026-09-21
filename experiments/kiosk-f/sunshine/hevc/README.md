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

### Experimental EOS correction

`0003-experimental-single-eos.patch` targets pinned FFmpeg d90e3a1. The existing
flush path resends the same end-of-stream MppFrame when output is temporarily
unavailable, and can create another EOS marker on later drain calls. The patch
records successful EOS submission, polls output without resubmission, and allows
the bufferless EOS marker past the regular in-flight image limit. Frame ownership
and teardown order are unchanged; no log message is suppressed.

Built the modified static library in an isolated disposable builder, then ran
encode-smoke with CYCLES=10 separately for H264 and HEVC on ROCK: all 20
open/encode/drain/close cycles produced 120 packets each. No invalid-memory-pool
warning appeared. The process-exit `cleaning misc group` message remains once per
codec process and still needs investigation. Final-cycle files passed independent
120-frame decode and first/last-frame gray reference checks; see
single-eos-results-20260921.json. Logs and generated before/after source copies:
/config/kiosk-test/builds/encode-eos-20260921. This supports duplicate EOS submission
as the tested trigger; it is not a general proof that every MPP ownership issue
is resolved.

This is an experimental patch, NOT yet applied by Containerfile or installed
Sunshine. Before promoting it: validate zero/short input and interrupted sessions,
check error/timeout handling and remaining buffer cleanup, rebuild actual Sunshine,
then exercise a real Moonlight reconnect. No decoder/RGA or default workflow
change is involved. The running kiosk remained untouched and active.

### Edge cases and cancellation, 2026-09-21

The smoke probe now accepts optional CYCLES FRAMES drain|cancel. Tested H264/HEVC,
0/1/2/5 input frames, drain or direct close, three cycles in each process (48
sessions). All processes terminated within their 12-second bounds and returned
success for the requested packet-count semantics. Every drained case had zero
invalid-pool warnings. **Direct close with pending frames still triggers invalid
pool warnings** for both codecs. Thus the EOS patch fixes tested draining, not
cancellation, and must not yet be promoted as a general Sunshine cleanup fix.
See single-eos-edge-results-20260921.json. Exit status alone is insufficient.

The remaining `cleaning misc group` message was checked in pinned MPP's
mpp/base/mpp_buffer_impl.c, mpp_buffer_service_deinit: it is the normal legacy
misc-group cleanup path. The separate `cleaning leaked group` branch identifies
remaining groups; that message was absent in these tests. Therefore misc cleanup
alone is not a diagnosed leak. This does not prove that long-running RSS is flat.

Next ownership audit must cover queued frames on cancellation: MPP destruction
can free KEY_INPUT_FRAME while FFmpeg still retains it in frame_list. Do not
silence warnings, blindly reorder deinit, or drop references without proving
which buffers remain owned by the caller. No production patch applied.

### Experimental cancellation ownership correction

`0004-experimental-frame-ownership.patch` applies after 0003. It records successful
MPP submission and recovers caller ownership from KEY_INPUT_FRAME on every
received packet, including EOS. Imported-buffer references are recorded separately
from MppFrame pointers. Before MPP destruction, still-submitted frame pointers
are detached from FFmpeg's cleanup list: the MPP queues own/free those frames.
The caller's imported-buffer reference and AVFrame are still released afterwards.
Frames never submitted or already returned remain caller-owned and are deinitialized
normally. This changes lifetime bookkeeping rather than muting warnings.

The MPP source at the pinned commit confirms that input is queued by pointer,
packet metadata returns KEY_INPUT_FRAME, and queued packet/frame destructors
release pending frames. These observations justify the tested ownership split;
other MPP versions or sync paths must not be assumed equivalent without testing.

Isolated static-library test on ROCK: all 48 prior short/empty/cancellation
sessions plus 20 full 120-frame sessions passed. No invalid-pool or leaked-group
messages in any of the 18 process logs. Normal process-exit misc-group cleanup
remains. Both final full bitstreams independently decoded 120 frames and passed
the gray reference checks. Evidence: ownership-cycle-results-20260921.json and
ownership-bitstream-results-20260921.json; raw logs under
/config/kiosk-test/builds/encode-ownership-20260921.

The two patches remain experimental and are not yet wired into production images.
Next: apply the exact patch files in a fresh build, test error paths and longer
same-process memory behavior, rebuild actual Sunshine, then real Moonlight
connect/disconnect testing. Working kiosk image/config were not modified.

### Full Sunshine cleanup candidate build

Containerfile.cleanup (6b5d831) applies exact 0003/0004 patch files with fuzz=0 to
an explicitly selected immutable HEVC builder, rebuilds the FFmpeg libraries and
Sunshine, and layers the binary over an explicitly selected runtime bundle.
It includes the smoke probe for isolated verification. Existing candidate recipe
and all production/release workflows remain unchanged.

Build started 2026-09-21 04:36 UTC on ROCK as systemd unit vyarm-cleanup-build,
CPUQuota=100%, MemoryMax=2G, Nice=10, podman network=none. Context and build.log:
/config/kiosk-test/builds/cleanup-candidate-20260921. Inputs: builder a332c7a...,
runtime bundle 8b48c818... (full IDs above/in BUILD-INTEGRATION.md); source revision
6b5d831. Intended output localhost/vyarm-kiosk:cleanup-candidate-20260921.
Status at this commit: building, not yet validated or activated. Next check build
exit/image provenance, then isolated probe and longer repeated codec sessions
using the binary built by this recipe. No kiosk image replacement performed.

Full cleanup candidate build completed successfully. Image
3fac48e2a9b718d0347acfa997196486963df120546a8339c4b0017fd42b6005,
revision label 6b5d831 verified. Actual rebuilt Sunshine isolated probe found
both H264 and HEVC encoders at 04:58 UTC. Probe used disposable state and loopback
listeners; original kiosk still active. Image has not replaced the live kiosk.

Started memory-probe.py in that exact image: 50 120-frame open/encode/drain/close
cycles per codec in one process, sampling RSS and open file descriptor counts.
Unit vyarm-cleanup-memory-test has CPUQuota150%, MemoryMax1G, RuntimeMaxSec500;
per-codec deadline240 seconds. Results/logs under cleanup-candidate-20260921.
At this commit the longer test is running; do not claim memory stability yet.

Measured lifecycle test completed: 50 cycles per codec, 6,000 encoded frames per
codec, both exit0, zero invalid-pool/leaked-group messages. Each process ran about
54 seconds. After five warmup cycles H264 sampled RSS ranged 11,360–37,544 KiB
and open FDs 8–26; HEVC 11,508–32,684 KiB and FDs7–28. Measurements sample different
lifecycle phases. Ten-cycle-window peak RSS did not grow across the run (H264 had
one transient higher peak); this supports bounded resource use over this short
test, not a long-duration leak-free guarantee. Final files from the exact built
image also passed independent 120-frame decode/reference checks. Raw measurements
and bitstream results are committed as cleanup-image-*-results-20260921.json.
No live deployment or real Moonlight session was performed.

## Paired Moonlight live test, 2026-09-21

Two bounded real sessions (35s/25s client process limits) successfully connected
and disconnected over the ROCK AP. Sunshine selected hevc_rkmpp for each actual
client connection and enabled video encryption. Moonlight used Intel iHD VAAPI
HEVC decoding on the ThinkPad. Requested1920x1080/60,8Mbps, no VSync/frame pacing,
windowed. Client metrics are in moonlight-live-results-20260921.json.
No invalid-frame-pool or leaked-group message appeared in the captured server
log. Short tests showed network jitter and host timing spikes; these are not
a controlled H264 comparison or a sustained60FPS result. Physical touch/audio
and subjective image quality were not evaluated.
The exact cleanup candidate binary was temporarily substituted under a600s
rollback timer. Original binary SHA256 b8deb1f5f15348fb6504cc9188ac641d2fc7df4e8df09ff20eb071608e8eef22
was explicitly restored and verified, timer cancelled, kiosk active. No native
container image setting, persistent codec default, pairing or firewall changed.
