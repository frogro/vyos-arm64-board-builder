# Moonlight stateless hardware decoder probe

Validated on ROCK 5B on 2026-09-29. This is a diagnostic candidate, not yet
a main release. The G test Containerfile now packages this candidate privately.

## Components

- Existing Moonlight 6.1.0 binary from commit
  `8369d1a0e11b999d4d1598f62ca5f6dea49602fb`.
- Private FFmpeg from `https://github.com/jernejsk/FFmpeg`, commit
  `904a85173fab816bb3c30652300efa93f2333657` (`v4l2-request-n7.1`).
- Kernel stateless Hantro decoder, `/dev/media1` and `/dev/video3` on this boot.
- Mesa/Panthor, Weston, Wayland; DRM PRIME import into EGL/GLES.
- Existing Profile G HDMI PulseAudio routing with timer scheduling.

The stock Debian FFmpeg did not expose this stateless decoder. Its
`h264_v4l2m2m` failure must not be interpreted as absence of hardware decoding.
RKMPP is not a substitute for the mainline V4L2 Request API on this kernel.

## Isolated build and launch

The build ran in a separate ARM64 Podman container using the receiver's
Debian generation. Build dependencies: build-essential, pkg-config,
libdrm-dev and libudev-dev. FFmpeg configure options:

```sh
./configure --prefix=/opt/ffmpeg-request --enable-shared --disable-static \
  --disable-doc --disable-debug --disable-autodetect --enable-libdrm \
  --enable-v4l2-request --disable-everything --enable-avcodec \
  --enable-avutil --enable-swscale --enable-avformat --enable-swresample \
  --enable-decoder=h264,hevc,aac --enable-parser=h264,hevc,aac \
  --enable-hwaccel=h264_v4l2request,hevc_v4l2request \
  --enable-demuxer=mpegts,h264,hevc,mov --enable-protocol=file \
  --enable-muxer=null --enable-encoder=wrapped_avframe \
  --enable-filter=null,anull --enable-ffmpeg
make -j4
make DESTDIR=/work/out install
```

Bind `/work/out/opt/ffmpeg-request` read-only to `/opt/ffmpeg-request` in the
test receiver, and set `LD_LIBRARY_PATH=/opt/ffmpeg-request/lib` plus
`DRM_FORCE_EGL=1`. Use Profile G's `decoder=hardware`, `codec=h264`,
`resolution=1920x1080`, `fps=60`, `bitrate=10000` options. Keep the existing
device permissions, persistent pairing directory and recovery timer.

Do not install these minimal libraries over the distribution libraries.
Before production integration, port/review the patches against the maintained
FFmpeg version and retain all required receiver codecs and software fallback.
This probe's HEVC build capability has not been validated by playback.

## Evidence required

The accepted run logged all of:

- `Format drm_prime requires hwaccel h264_v4l2request initialisation`
- `Using V4L2 media driver hantro-vpu (6.18.50) for S264`
- `Renderer 'EGL/GLES' with 'DRM' backend chosen`
- actual stream reconfiguration to `1920x1088`, `pix_fmt: drm_prime`

The Moonlight process held `/dev/media1`, `/dev/video3` and render-node FDs.
The user confirmed correct colors, fluid motion and synchronous tone/flash.
Do not treat the small built-in test decode alone as live-stream success.

Software and hardware 1080p60 comparisons used the same real 60fps flash/tone
fixture, LAN and 10 Mbps setting. The build container was paused during the
software baseline and finished before hardware measurement. Whole-receiver
CPU samples were 145–154% software versus 45–49% hardware (100% is one core).
These are short sampled comparisons, not end-to-end latency measurements.

Evidence remains under `/config/receiver/g-live-20260928/state/` on ROCK:
`moonlight-software60.log`, `moonlight-hardware60.log`, and
`moonlight-hardware30.log`. Build source/output lives in the sibling
`ffmpeg-request/` directory. The live default images were not modified. The subsequent G testbuild packages
this candidate for H.264 auto/hardware selection only. A separate no-device
container decoded all ten frames of a synthetic H.264 clip through the private
FFmpeg software decoder, verifying that software decoding remains available.

## Pairing GUI regression (2026-09-29 installed-image check)

The GUI reported no functioning hardware decoder although isolated Request
conformance tests passed. Its startup environment excluded `mode=pair`, so the
built-in capability probe loaded distribution FFmpeg and tried VAAPI,
VDPAU and stateful V4L2 M2M instead of stateless V4L2 Request.

The private Request libraries and `DRM_FORCE_EGL=1` now also apply to Moonlight's
pairing GUI with auto/hardware decoder selection, regardless of the configured
stream codec: the GUI probes capabilities independently of the streaming command. Explicit
software mode and other receiver methods retain their previous environment.
The qualified receive-mode codec scope remains H.264. Merely starting the GUI
is not hardware-decoder evidence; require successful V4L2 Request test decoding.

The corrected live GUI selected `hevc_v4l2request`, opened `rkvdec (6.18.50)
for S265`, and decoded/output its test frame successfully. This validates the
GUI capability probe, not a new HEVC stream acceptance. HDR/unsupported-format
probe messages remain; no driver replacement or host permission changes were
needed. The sender was offline and the Kiosk was restored afterwards.
