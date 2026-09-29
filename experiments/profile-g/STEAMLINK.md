# Steam Link in the isolated A–D/F/G test branch

Integration branch: `test/profile-g-steamlink-integration-20260929`.
This is an additional receiver method, not a replacement for F, Moonlight,
Miracast or AirPlay. The official Valve ARM64 client is pinned to 1.3.32.316
and its archive and executable SHA256 are verified during the build.
Automatic client updates and host udev/USB-redirection helpers are not run.
Valve's licenses and third-party notices remain in `/opt/steamlink`.

## Native CLI

Use a **separate receiver container**, with the tested G runtime tag shown in
its `runtime.json`. Keep the existing kiosk configuration and disable it only
when activating G; the CLI rejects simultaneous ownership of the same DRM
card. Start with `commit-confirm`, verify the receiver, then `confirm`/`save`.
Do not delete the working kiosk configuration or previous installed image.

On the currently tested ROCK, with the common G display/audio grants already
configured (see IMPLEMENTATION.md), the Steam-specific settings are:

```
set container name receiver receiver method steamlink
set container name receiver receiver mode receive
set container name receiver receiver decoder hardware
set container name receiver receiver codec hevc
set container name receiver receiver resolution 1920x1080
set container name receiver receiver fps 60
set container name receiver receiver bitrate 20000
set container name receiver capability mknod
set container name receiver device heap source /dev/dma_heap/system
set container name receiver device heap destination /dev/dma_heap/system
set container name receiver device hantro source /dev/video2
set container name receiver device hantro destination /dev/video2
set container name receiver device hantro-media source /dev/media0
set container name receiver device hantro-media destination /dev/media0
set container name receiver device rkvdec source /dev/video3
set container name receiver device rkvdec destination /dev/video3
set container name receiver device rkvdec-media source /dev/media1
set container name receiver device rkvdec-media destination /dev/media1
```

Device numbering is board/kernel dependent: these media/video numbers are the
observed ROCK mapping, not a portable enumeration rule. Explicit render-node,
DRM-card, seat/VT, selected HDMI audio and input grants are still needed.
`allow-host-networks` is required for local discovery. No net-admin capability
is needed for Steam Link. The runtime creates `vidbuf_cached` **inside the
container** from the explicitly granted system heap; it never changes host
node permissions. `mknod` does not grant access to unlisted device numbers.

The persistent `/config/...` volume at `/state` retains pairing and settings.
The GUI selects/pairs the Windows host. `mode pair` opens the same Steam GUI;
`host` and `app` remain Moonlight-only and are rejected for Steam Link.

`codec auto` currently means H.264; HEVC is explicit. AV1 and >1080p60 are not
qualified and are rejected. On each start the adapter applies CLI resolution,
frame rate, bitrate and decoder/codec preference to the known protobuf fields,
backs up the first previous settings file, and preserves unrelated fields and
pairings. Malformed settings fail without overwriting them. GUI changes to
these CLI-owned fields last until the next container start.

## Decoder guards and fallback

* `hardware`: exact executable/hash, private-library manifest, FFmpeg Request
  ABI and device checks must pass; otherwise startup fails with an explanation.
* `auto`: uses the hardware adapter when preflight passes; otherwise starts
  H.264 software decoding and records the reason.
* `software`: H.264 with distribution libraries, no Request/HEVC adapter.
  Select `codec h264` or `auto` together with this fallback.

`/state/steamlink-runtime.json` records the selected policy and fallback reason;
it is **not** proof that a stream actually used hardware. Confirm rkvdec/S265
or Hantro/S264 in the container log and decoder device FDs during streaming.
Auto fallback covers preflight failures; it does not promise recovery from an
arbitrary kernel fault or mid-stream driver hang. For that case stop G and
restore the retained kiosk, or explicitly select software mode.

Qt's UI uses a private XWayland socket without TCP; SDL video uses Wayland.
The client is unprivileged, with explicit device groups. The interface-list
crash guard and decoder bridge are loaded only into this pinned client.
The HEVC Pi-revision workaround affects only the verified shell+0x1405cc call;
other `/proc/cpuinfo` readers see the real hardware. This remains an experimental
compatibility adapter; updating the client requires a new audit.

The private FFmpeg includes Detlev Casanova's HEVC EXT SPS short/long-term RPS
backport from Collabora commit `a8eb4b006d055f0be43d4a03d87472d2f199f177`.
It does not replace host libraries, GStreamer, Chromium or F's FFmpeg.
Conformance results: 44/44 and 500/500 frames match software reference; H.264
and the actual Steam HEVC stream each retain 360/360 matching frames.
See `live-test/steamlink/ffmpeg-rps/` for attribution and measurements.

## Minimizing on Windows

On Legion, **Steam minimieren** changes the received HEVC elementary stream
from 1920×1080 to 340×1080 black frames. Capturing compressed packets before the
ROCK decoder, then decoding the final VPS segment with an independent x86
software decoder, gives 30 identical frames with no decode errors. RGB output
is all zero. Thus the black image exists before ROCK decoding/display: the
problem is in Windows Steam's capture/stream selection, not a Hantro/rkvdec
rendering failure. The specific Windows capture API/driver cause remains open.

Use **Big-Picture-Modus verlassen** to reach the desktop instead. The bounded
comparison retained 1920×1080 and ~59.74 decoded fps. H.264 and HEVC both showed
the bad minimize behavior, so switching codec is not a fix. No Windows driver,
iGPU, global Steam or host audio setting was changed to work around it.
Similar upstream user reports are supporting context, not proof of our cause:
https://steamcommunity.com/app/353380/discussions/0/1368380934281202270/

During real 1080p60 video, measured H.264 averaged 59.77 fps for 190 seconds and
HEVC 59.73 fps for 165 seconds. Idle Big Picture drops to ~22 fps and returns to
60 with activity. These counters measure decoded frames, not a fresh subjective
latency/A-V sync acceptance. The user separately confirmed both codecs' image,
colors, motion and synchronized audio. Long-duration and installed-image tests
remain open.
