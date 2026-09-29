> Historical experiment notes. The guarded integration is now documented in
> ../../STEAMLINK.md; the diagnostic preload sources below are not packaged.

# Steam Link live investigation (not production integration)

`ifaddrs-guard.c` is loaded only into the Steam Link process through
LD_PRELOAD. It omits addressless interface records, which Valve runtime
1.3.32.316 otherwise dereferences on VyOS's pim6reg interface. It retains
all address-bearing records, including Tailscale IPv4/IPv6, and frees the
original libc list when its copied view is released.

Build inside the matching ARM64 Trixie runtime:

```sh
cc -Wall -Wextra -Werror -O2 -shared -fPIC -o ifaddrs-guard.so ifaddrs-guard.c -ldl -pthread
python3 check-guard.py
LD_PRELOAD="$PWD/ifaddrs-guard.so" python3 check-guard.py
```

Compare the reported lists: only null-address records should disappear.
The script exercises 1000 calls across four threads. Do not install the
library in /etc/ld.so.preload or apply it to unrelated processes.

The separate video-start issue requires scoped DMA-heap device access.
See RESEARCH.md for the live experiment and remaining acceptance criteria.
The heap alias is not a CMA allocator and must not imply hardware decoder
support. No Steam receiver image/CLI integration is approved by these tests.


## Decoder diagnostic, 2026-09-29

`decoder-trace.c` logs FFmpeg decoder/device selection without changing it.
`decoder-request-bridge.c` is an isolated proof of concept for the pinned
ARM64 Steam Link 1.3.32.316 and private FFmpeg libavcodec61/libavutil59 build.
It translates device type 8 (DRM) to 13 (V4L2REQUEST), ignoring the DRM device
argument. These enum values were checked in the pinned build. This is NOT a
general-purpose preload library; never install globally or use with another
FFmpeg ABI. Production integration needs version/device checks, opt-in scope,
and safe fallback. Do not package this diagnostic as a finished fix.

Build in the ARM64 diagnostic container:
`gcc -shared -fPIC -Wall -Wextra -Werror decoder-request-bridge.c -o decoder-request-bridge.so -ldl`

Tests: distro FFmpeg -> H.264 software; private request FFmpeg without bridge
-> repeated device creation failure -14; private FFmpeg plus bridge -> Hantro
S264, DRM PRIME frames, /dev/media0 and /dev/video2 open in Steam's process.
Audio decoder initialized at 48kHz stereo. This does not establish audible
synchronization, delivered 60fps, HEVC, AV1, or sustained stability.


## HEVC capability experiment

`decoder-hevc-probe.c` adds a narrowly scoped diagnostic override: only the
fopen("/proc/cpuinfo", "r") call returning to shell+0x1405cc receives a
synthetic Revision line. All other reads use the real procfs. This exposes
an incorrect Pi-revision gate in the official ARM64 client's HEVC selection.
The actual decoder is independently proven on RK3588; this is not suitable as
a general hardware capability detector or a production-wide preload.
Tested shell SHA256: `b245adfccc2cda43e405194cd66615c30ffdae6f7416b7db0579d5c161a3f7fd`.
Production work must check the exact binary hash/ABI, or preferably replace
this workaround upstream with actual device capability probing. A future
binary must fail closed for this experimental override, not reuse offsets.

The gate special-cases AV_CODEC_ID_HEVC (173), opens /proc/cpuinfo, scans
"Revision : %x", extracts bits12..15 and requires a value >2. On this ROCK the
field is absent. The earlier device-type alias in advertised hw config was
unnecessary. The working experiment combines only the original device-create
bridge, private Request FFmpeg and this call-site-specific capability probe.

HEVC preference was set in a backed-up streaming_settings.bin using the
CStreamingClientConfig protobuf field13=true (0x68,0x01), whose schema is in
https://github.com/SteamDatabase/Protobufs/blob/master/steam/steammessages_remoteplay.proto
The --enable-hevc shell argument alone had not changed the persisted setting.
Keep this binary-settings edit diagnostic; use a supported UI/adapter for
integration and preserve unrelated settings.

Live result: avcodec_open2(hevc)=0, rkvdec6.18.50/S265, /dev/media1 and
/dev/video3 held by Steam player; 1920x1080 output, audio initialized48kHz
stereo. Missing video4 during enumeration did not prevent selection of video3.
Subjective acceptance is tracked in RESEARCH.md separately.


## Runtime guard and rate measurement

Run `python3 check-runtime.py --shell /probe/steamlink/bin/shell --library-dir /request-lib`
before enabling the experimental preload; any mismatch exits nonzero. The
matching live runtime passed and /bin/true as a substitute was rejected.
`decoder-hevc-rate.c` adds five-second successful-decoded-frame counts to the
HEVC diagnostic. These are decode rates, not independent display-rate proof.
A matching user observation of ~60FPS in the Steam overlay was obtained.
The separate Wayland-listener experiment was discarded after a SIGSEGV and
must not be included in a packaged runtime.


## Idle/motion comparison, 2026-09-29

`comparison-20260929.json` records five-second decoder counts for matched
H264/H265 tests. On Legion's idle Steam Big Picture UI both settled around
22fps after ~25seconds. `input-motion-probe.c` injects alternating left/right
key presses only during the consented diagnostic window (50-80seconds),
causing UI movement and restoring ~60fps without restarting the decoder.
About25seconds after input stops the rate returns to22. Thus this observation
does not establish a sustained-motion decoder throughput limit.

The probe targets the last SDL window if keyboard focus is absent and runs
in SDL_PeepEvents on the application's event thread. Never ship/preload it
in a normal receiver; it generates input. A separately built long variant
used 5seconds delay and480events (240seconds) for the bounded motion run.
No SDL/Pi capability override is installed globally.

See ffmpeg-rps/ for the separate HEVC correctness defect found during this
investigation, exact isolated backport and frame-reference comparisons.

## Tested desktop switch

For the tested Legion/Steam Link runtime, use **Steam menu > Ein/Aus >
Big-Picture-Modus verlassen**, then switch to the desired Windows application.
`Steam minimieren` reproducibly yields a narrow340x1080 stream with both
Hantro H264 and rkvdec HEVC. Decoder throughput continues near60fps; the exact
common capture/selection bug is unresolved. Reconnect restores Big Picture.
Do not implement an automatic host restart or silently switch codecs as a
workaround. See desktop-transition-20260929.json and RESEARCH.md.

Image integration remains outstanding: guarded Steam binary/adapter/private
libraries/device access/state management, native CLI selection, and the RPS
backport must be packaged and retested before claiming Steam support in the
combined SD/ISO. Existing image success gates only cover currently packaged
receivers; live-only diagnostics do not become image features automatically.
