# ROCK 5B full-image regression session, 2026-10-05

Live system: VyOS 999.202610042340, Linux 6.18.54-vyos, 512 MiB CMA,
installed from build 37244477172. Test window began 09:47:26 Europe/Berlin.
This is a development record, not the user manual or a qualification of other boards.

## Confirmed integration faults and corrections

- Signage's generated nftables chain had invalid closing syntax. Generate a
  multiline ruleset and check it before stopping the working service.
- The pinned Anthias utilities and Channels use redis:6379 independently of
  Celery settings. Bind Redis to loopback port 6379 and provide the container
  alias; the previous port 16379 produced management/login errors.
- Sunshine's input bridge must create its container-private /dev/input when
  no physical input mapping created it. Never recreate a vanished container
  parent or follow a symlink.
- Stop signage containers before terminating attached podman processes and
  their fuse-overlayfs helpers. Systemd uses KillMode=mixed so the supervisor
  can perform this ordering. A service restart no longer produced the earlier
  SQLite disk-I/O / disconnected-mount shutdown exceptions.
- Explicitly pause and unload the previous video before removing its element.
  Before this change, repeated UHD AV1 playback exhausted contiguous buffers;
  afterward the repeated test stayed on V4L2VideoDecoder without new CMA errors.
  Some frame drops remain; this does not certify every 4K stream as smooth.
- KVM GStreamer uses its own boot-local registry. The inherited root registry
  omitted mpph264enc although the plugin was present. A fresh registry exposed
  the encoder; the corrected service published a decodable 1080p H.264 stream.

## Executed checks

- Authenticated management/settings/status and playlist endpoints; anonymous
  management redirect and missing-CSRF rejection.
- Web rotation and mute changes propagated through native VyOS commit/save.
  Remote view-only disabled input authorization; control restored it.
- Backup contains media, database/settings and scoped VyOS display/remote
  settings. Restore reverted deliberately changed rotation/mute and reinstated
  the original schedule and remote settings. Login worked afterward, all 18
  assets returned, and all 16 original media SHA-256 values matched.
- Real 3840x2160 H.264/AAC upload was processed with correct metadata. The
  temporary upload was deleted. A new YouTube URL was stored as webpage with
  is_processing=false; no download was queued. Test URL was removed.
- Management container paused; kiosk/container restarted while management was
  unavailable. Cached photo/video playlist continued changing. Management
  recovery and original asset activation were verified.
- Chromium CDP reported V4L2VideoDecoder for H.264, HEVC, VP9 and AV1 UHD,
  HEVC 10-bit, and H.264/HEVC 60-fps test clips. AV1 buffer exhaustion occurred
  before the player cleanup fix; its repeat used hardware but had some dropped
  frames. The first sampling script did not serialize frame-quality getters,
  so its empty quality objects are not evidence of zero dropped frames.
- Native CUPS/Gutenprint RX1 job RX1-9 completed (one 4x6 sheet). Physical print
  appearance requires the user's confirmation. VirtualHere attached the RX1
  to the ThinkPad, then released it. CLI rejected simultaneous ownership of
  the same USB port; CUPS was ready after return. No license key was installed
  or changed during this session.
- Temporary WireGuard tunnel: five pings in each direction, no packet loss;
  handshake and counters verified. Interfaces and temporary keys removed.
  ThinkPad AppArmor initially rejected the test-key location; placing the key
  in a root-owned file fixed the test without changing AppArmor policy.
- Tailscale readiness passed; no account login or Tailnet routing test.
- Moonlight received the ThinkPad desktop and audio using rkvdec H.264 hardware
  decoding. AirPlay and Steam Link runtimes started; Steam Link selected
  v4l2request with the required Hantro device grant. No Apple/Steam sender was
  available for full protocol tests. AirPlay emitted a startup Wayland
  fullscreen assertion without terminating; full sender validation remains.
- Miracast correctly refused to take an administratively active WLAN interface.
  Router wireless configuration was not altered to force this test.
- HDMI capture detected 1920x1080/60. uStreamer produced a valid JPEG;
  GStreamer (after registry fix) and FFmpeg each published a decodable H.264
  RTSP stream. USB gadget controller was not attached to a peer, so no new
  end-to-end keyboard/mouse/virtual-media test was possible.

## Source validation

Kiosk 118 tests, receiver 44 tests, signage 19 tests, native CLI combinations
against pinned upstream, and the affected KVM/print/build/update/kernel/board
selection tests passed. The local image-info test first lacked tabulate;
with its declared dependency installed in a temporary test directory it passed.

The existing Pi 5 run 37276373847 was cancelled at the user's request. The
Rolling resolver selected source 414b5ae6d9f568d218880b1a3c4293f7ef193df7,
kernel 6.18.54-vyos and reusable base 37244478821 for the replacement builds.

## Reboot and VPN follow-up

The corrected live image rebooted successfully. Signage, kiosk and Sunshine
input bridge were active with zero automatic restarts and no failed systemd
units. Signage stopped cleanly during shutdown; the former SQLite and
fuse-overlayfs exceptions did not recur. Existing early RK3588 probe/dependency
messages and FRR disconnects during shutdown are not claimed to be fixed.

An actual WireGuard client was rejected by the signage firewall before its
network was allowed. Adding that network through VyOS enabled HTTP access to
the management login. The temporary allowlist entry and tunnel were removed.
The FFmpeg KVM backend also produced a stream decoded successfully for five
seconds. All temporary KVM/print/USB/receiver configuration was removed.

## Final post-boot codec repeats

Each of the following clips was sampled for two minutes after reboot. All used
V4L2VideoDecoder at 3840x2160; no new CMA allocation failures or display-IOMMU
faults occurred. Frame increments are sampled across playback loops, not a
complete frame-by-frame capture:

- 4K-Test h264-60.mp4: 0/6153 sampled frame increments dropped (0.00%).
- 4K-Test hevc-10bit.mp4: 0/3057 sampled frame increments dropped (0.00%).
- 4K-Test av1.webm: 85/3135 sampled frame increments dropped (2.71%).

Both reviewed CLI recipe pins were refreshed for the KVM runner change. The
first GitHub check caught the still-old kiosk pin after the receiver pin had
already been updated; all lifecycle tests themselves passed in that run.

The follow-up GitHub integration run 37284714269 passed on main 471166c.
Matching fixes are on the expanded Pi/E52C branch at cecd38f. The original
saved configuration was restored and compared with the pre-test copy, ignoring
comments and blank lines; no configuration differences remained.

A single conmon stderr Broken pipe at 08:37:43 UTC accompanied a short-lived
podman exec during restoration, not termination of the kiosk container. This
is recorded separately from the corrected signage stop-order failure; the
journal is not claimed to be warning-free.

Full builds with signage were excluded from the automatic artifact publisher.
Remove that exclusion and dispatch the replacement builds with direct release
upload disabled: the completion workflow then performs the verified, retryable
upload with split IMG support in the builder repository.

The one-hour window ended at 10:47:26 Europe/Berlin. Final authenticated pages
(management, settings, system information, status, playlist) returned HTTP 200.
The final monitoring samples reported all three services active, NRestarts=0,
and no failed units. The user's original playback schedule remains restored.
