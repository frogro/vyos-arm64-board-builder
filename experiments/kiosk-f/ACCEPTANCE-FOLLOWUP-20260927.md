# Profile F follow-up, 2026-09-27

## Confirmed changes

- Preserve selected input AddDevice ordering when regenerating the Quadlet.
  A Sunshine audio/input policy change retained the container ID and Chromium
  PID in the live test; 9 input-reconciler tests include this regression.
- Private per-user PulseAudio session is started by both X11 and Wayland.
  Wayland loopback test captured 146922 samples with peak 1000 from the injected
  440 Hz signal. This is numeric loopback evidence, not a subjective speaker test.
- New-install setup detects MPP and playback devices by capability. MPP needs
  /dev/mpp_service, /dev/dma_heap/system and readonly DT compatible mounted at
  /run/mpp/compatible for this runtime. No capture PCM or remote access is enabled.
  Existing configurations are not automatically migrated by setup-kiosk.
- 95 kiosk unit tests pass. These changes are on the isolated ADF test branch.

## Network recovery and actual Sunshine sessions

The loose MT7922 card returned after PCIe rescan without reboot. AP and DHCP were
missing from the already-saved configuration before the latest image update.
Only wlan0 and VYOS-AP DHCP entries were restored from the Sept26 backup and saved.
The rollback baseline was updated to preserve them. No firewall broadening.

Historical Sept21 HEVC results confirm two real Moonlight sessions through the
ROCK AP to its LAN address. For this new test the seven Sunshine TCP/UDP port
mappings were explicitly rebound to the AP address 10.3.141.50. ThinkPad routing
confirmed wlan0-side access from 10.3.141.52 despite its separate Fritzbox LAN.
Wait for serverinfo HTTP 200 after restart before pairing: early attempts received
connection-refused. The PIN pairing then succeeded through the CLI controller.

Runtime candidate: localhost/vyarm-kiosk:audio-hevc-test3-20260927,
image ID 38c82b5d729a4abed2f1fc9ecc89d3a1462fc61de9db27c22ce0f9e5524589c4.
It copies /opt/vyarm/experimental/sunshine-rga to /usr/bin/sunshine, registers
/opt/mpp/lib with ldconfig, grants Sunshine cap_sys_admin+p for KMS, and includes
both audio-enabled session launchers. RGA conversion remains opt-in and disabled.
The final source audio helper additionally handles process/probe errors; this
small robustness update is not yet in candidate3. A new release artifact is needed.

With DRM Wayland active and transient view-only Sunshine policy:
- HEVC: 13:23:15 UTC CLIENT CONNECTED; KMS capture; hevc_rkmpp 8-bit SDR encoder;
  hardware decode in ThinkPad Moonlight; first audio packet received; disconnect
  13:23:36 UTC.
- H.264: 13:23:57 UTC CLIENT CONNECTED; KMS capture; h264_rkmpp 8-bit SDR encoder;
  hardware decode in ThinkPad Moonlight; first audio packet received; disconnect
  13:24:17 UTC.
- Both requested 1920x1080, 30 fps, 4000 kbps, windowed, encryption enabled.
- PulseAudio created sink-sunshine-stereo and Opus 48 kHz stereo initialized.

These are short transport/decode tests, not a sustained FPS or visual-quality
acceptance. Audio packets can contain silence; audible end-to-end content still
needs verification. KMS cursor plane is absent. Portrait orientation, remote input
mapping, HDR/Main10 encoding and reconnection endurance are not accepted here.
The normal CLI DRM-Wayland remote-access guard is deliberately still in place.

## Remaining work

- Package the proven HEVC runtime and device mappings reproducibly, then add
  capability-gated Wayland remote mode after rotation/input validation.
- CLI should configure access policy, listening address, pairing and audio;
  Moonlight establishes the stream. AP/LAN require no VPN. Offsite access can use
  Tailscale or WireGuard; do not hard-code a VPN dependency or expose public ports.
- Keep display backend and network access selection independent.
- Profile D negotiated-colour GStreamer test used CPU videoconvert while RGA
  experimental_full_csc=N, roughly 120 frames / 12.56 seconds. An RGA-enabled
  attempt hit RTSP before publisher readiness; its performance is still untested.
- Fresh SD and decoder endurance tests remain deferred by the user.

## End-to-end audio follow-up

Two source tones (697 and 1209 Hz, one second each with one second silence,
48 kHz stereo PCM, source amplitude 1000) were played into Sunshine's stereo
sink on the ROCK during HEVC Moonlight streaming over the AP. The ThinkPad's
PipeWire speaker-monitor capture (not microphone) recorded 1195264 frames,
peak 1135. Frequency analysis measured tone amplitudes 1016.01 and 1004.89.
Both tones therefore traversed Sunshine/Opus/network/Moonlight/output.
The user independently confirmed seeing the picture and hearing audio.
Remote mouse input was intentionally disabled by view-only policy; its absence
in this run is expected and is not a remote-input regression test.
Tailscale client installation on ThinkPad was authorized and completed; ROCK
native service tailscale configuration was enabled. Authentication/testing of
the current ROCK node is pending. No offsite-streaming success claimed.

## Tailscale follow-up

Both current nodes authenticated with the user's existing tailnet. The ROCK
registered a new identity because its active state directory did not contain the
previous identity. The old offline node remains; it has not been deleted.
State for future updates is /config/tailscale/state/tailscaled.state and must
be retained together with the native service tailscale configuration.

Sunshine port bindings were temporarily moved from AP to the ROCK tailnet IPv4
address. ThinkPad route lookup confirmed tailscale0/table52 and source tailnet IP.
Serverinfo returned HTTP200, two HEVC Moonlight sessions connected and decoded.
Tailscale peer counters confirmed traffic. Its direct encrypted endpoint was
on the local Fritzbox LAN; this was NOT a geographically remote/DERP test.

The repeated tone test over Tailscale captured 1053184 frames at 48 kHz with
peak 1115 and tone amplitudes 1015.62 (697 Hz) and 1001.49 (1209 Hz).
Therefore non-silent content traversed the VPN as well as Sunshine/Moonlight.
View-only remained intentional; no remote mouse acceptance claimed.

Normal kiosk/runtime/policy and temporary port bindings were restored after
these tests. Preserve native Tailscale enablement and private identity for future
remote tests. A future remote test from another network must still validate NAT
traversal/relay throughput and latency. No public port forwarding was configured.

## Samsung hotspot / relay test

User moved ThinkPad to Samsung hotspot. Verified Ethernet DOWN, only WLAN IPv4
10.174.69.115/24 with default gateway 10.174.69.200, plus tailscale0. No local
Fritzbox or ROCK AP route remained. Tailscale ping to ROCK used DERP(ams), initial
220 ms then 69 ms; no direct connection was established. During streams CurAddr
was empty and peer traffic counters increased (local Relay ams, remote Relay fra).
Thus this additionally covers an actual relay path, not merely same-LAN VPN.

Temporary Sunshine bindings used only the ROCK tailnet IPv4. PIN pairing worked;
container saw bridge source due to NAT. Short 1080p30 hardware-encoded/decoded
streams, terminated intentionally by timeout:

| Codec | Requested bitrate | Packet size | Logged network-dropped frames |
| --- | --- | --- | --- |
| HEVC | 4000 kbps | default | 2 |
| H.264 | 4000 kbps | default | 16 |
| H.264 | 2000 kbps | 1024 bytes | 2 |

These counts mostly reflect startup in different short sessions, not normalized
loss rates or a controlled codec comparison. Lower bitrate and packet size were
changed together: the result does not identify which change helped. All three
sessions received video and audio. HEVC non-silent tone capture at ThinkPad output
recorded 864000 frames at48kHz, peak1048, tone amplitudes1018.36 and1008.16 for
697/1209Hz. No microphone captured. No mouse input enabled (view-only).

Hotspot test has its own rollback baseline including enabled Tailscale, so cleanup
does not remove the only remote management path. Normal kiosk and its original
Sunshine state are restored after test. No public router port forwards needed.
Remaining acceptance: remote control/rotation and sustained motion/latency tests.

## Wayland remote-input investigation

The control-enabled candidate creates libvirtualhid Keyboard, Mouse and Mouse
(Absolute) through /dev/uinput. Their host evdev nodes were missing inside the
container. Host udev multicast also does not reach the container network namespace.
These are separate problems from Sunshine's input-policy switch.

Bounded live proof: a temporary native Quadlet device-cgroup rule `c 13:* rw`,
host-created nodes for only the three virtual devices, and selective forwarding
of their actual udev add messages into the container network namespace caused
Weston to register all three at 14:11:49–50 UTC, without a compositor restart.
Read-only access was insufficient for seatd/libinput; CAP_MKNOD stayed absent.
No entire /dev/input bind mount or general udev forwarding was used.

Ownership can be checked without trusting device names: duplicating the running
container Sunshine process's uinput file descriptions via pidfd_getfd and querying
UI_GET_SYSNAME returned its actual input12–input16 devices. A production helper
must use this association, validate virtual sysfs paths, handle removal/recreation
and container PID changes, and refuse unrelated devices. This is not yet an
installed service or a CLI release of Wayland remote control. The Moonlight
control session connected. The user subsequently confirmed mouse and keyboard
input, but reported difficult mouse control and feeling trapped in the window.
Therefore basic input delivery is accepted; usability and portrait-coordinate
acceptance remain open. The bounded client process has already exited.
Moonlight supports Ctrl+Alt+Shift+Z to release capture, Q to quit, and
--absolute-mouse for a separate desktop-control comparison. Do not infer a
coordinate defect solely from the mouse-capture complaint.

## Update preservation audit

The installed image_installer.py copies the entire DIR_CONFIG tree using
copytree(symlinks=True, copy_function=copy_preserve_owner, dirs_exist_ok=True)
when configuration migration is selected. The live kiosk state mount originates
at /config/kiosk/state; native Tailscale state is /config/tailscale/state.
AP configuration is in saved config.boot. All three therefore belong to the
normal migration set. Actual next-image identity/pairing comparisons remain
required; this source audit is not an update acceptance result.

## Profile D RGA performance follow-up

Same live HDMI input: BGR 1920x1080 at 60 Hz. Native CLI temporary GStreamer
backend, negotiated colour, 8000 kbps, GOP60, listener127.0.0.1:18080.
Waited for MediaMTX to report its RTSP publisher online before reading frames.

- experimental_full_csc=Y selected v4l2convert plus mpph264enc. FFmpeg received
  and decoded 600 distinct output frames in 10.964 seconds including connection
  and probing; steady progress was approximately 60 frames per second. Stream
  metadata: H.264 High, limited-range BT.709, 1920x1080. Exit0.
- experimental_full_csc=N selected CPU videoconvert plus the same encoder.
  FFmpeg received/decoded 120 frames in 17.447 seconds including startup/probing;
  progress increments were about ten frames per second. Exit0. Metadata retained
  limited range and BT.709 matrix/primaries, with sRGB transfer from negotiated caps.
  An earlier eight-second ffprobe readiness timeout was not an encoder crash.

These are short throughput checks, not latency, sustained stability or objective
pixel-quality acceptance. They establish a performance benefit versus this
GStreamer CPU-conversion fallback, not versus every existing D backend. The prior
FFmpeg MPP baseline already reached 60 fps. No default backend was changed.

After testing: module parameter restored N, temporary D configuration removed,
original Wayland kiosk image restored, Tailscale remained active. A local
integration/main-tested-df-20260927 branch starts from origin/main13cf40e and
contains only the optional D candidate so far. Its KVM CLI/input and feature
profile tests pass (23 tests). Main and published workflows remain unchanged;
F packaging and remote-control acceptance are still outstanding.


## Remote-control latency: user feedback and client statistics

User clarified that pointer movement was delayed/jerky, not merely captured.
The control-test client summary records 13.52 incoming/decoding fps, 13.50 rendering
fps, host processing latency min/max/mean246.8/305.5/282.4ms, network61ms
(variance13ms), network drops0.00%, jitter drops0.17%, decoder0.46ms,
frame queue0.11ms, renderer2.68ms. Hardware input delivery therefore passes,
but interactive performance does not.

This cannot reasonably be attributed solely to the mobile/DERP path: the earlier
AP H.264 log already recorded13.75fps and288.4ms mean host processing with2ms
network latency; tailnet-over-LAN audio test13.59fps and282.6ms with1ms network.
Both H.264 and HEVC show the host bottleneck. Investigate KMS acquisition, CPU
conversion/scaling and encoder queueing separately. RGA is a candidate, not yet
a demonstrated Sunshine performance fix. Profile D's RGA result is not proof
for this differently captured and possibly scaled/rotated frame path.

The next comparison should hold resolution, codec, framerate and bitrate constant,
measure host processing and frame rate, and change only the converter or capture
path. Do not declare full F remote-control acceptance based on input delivery.
