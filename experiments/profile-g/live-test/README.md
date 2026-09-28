# Bounded live-test recovery (ROCK-specific harness)

This is a diagnostic harness, not release CLI integration. Units are installed
in `/run/systemd/system` and do not enable tests at boot. The live backup at
`/config/receiver/g-live-20260928/backup` must match the current system.

Install recover.sh as `recover-v2.sh` in that directory. Manual recovery must
use `systemctl start --no-block profile-g-recovery.service`; never run radio
restoration inline in SSH. The legacy live rollback.sh now delegates to this
service as well.

Before a test, start/restart profile-g-recovery.timer and confirm it is active.
The 120-second deadline runs on ROCK. The service serializes recovery, skips
resetting an already-restored AP, restarts hostapd after a necessary reset,
checks MAC/IPv4/interface/AP state and kiosk service, and only then disarms the
timer. Failed recovery retries every ten seconds, with a 90-second per-attempt
limit. This cannot recover a dead kernel or physically missing WLAN device.
Do not launch a new test while recovery is active.

ThinkPad also needs a separate local timer to stop the sender and reconnect
homebase. This limits exposure when its only uplink is the same WLAN radio.
It does not make concurrent STA/P2P immune to firmware crashes. Prefer wired
management. Recheck homebase route before every attempt; reject VyOS-AP.

## Live checks 2026-09-28

- Recovery while AP already restored: explicit skip, no radio reset.
- Deliberate AP stop + wlan0 DOWN: 10-second temporary timer restored AP and
  kiosk; recovery verified at 13:06:01. Override removed afterwards.
- Next Miracast attempt discovered VyOS-TV and reached WAIT_SOCKET, but
  disconnected before streaming. Management remained available; recovery
  completed at 13:08:22. No successful audio or latency result from this run.
- ThinkPad microphone opened successfully. Initial 100% gain clipped heavily;
  capture is not by itself proof of received Miracast audio.

These checks do not establish recovery after power loss or a WLAN firmware
failure. No driver investigation or replacement was performed in this task.

Audio follow-up: the current F kiosk exposes no `/dev/snd` devices and therefore
only auto_null in PulseAudio. HDMI0 has ELD for RTK FHD HDR with one audio format;
HDMI1 has none. This is separate from G: the G launcher explicitly passes sound
nodes. Playing a marker through the F null sink is not acoustic proof. The
ThinkPad microphone gain is restored after each bounded capture.

Direct acoustic baseline passed: host `aplay -D plughw:1,0` played the marker WAV
(exit 0). ThinkPad internal microphone at temporary 20% gain captured the
600/1200/1800 Hz sequence at seconds 5/9/14 of the recording. Windowed FFT
relative peak scores were 104/119/102 respectively, compared with below 1
outside the marker intervals. Startup transient clipped; subsequent tone
intervals did not. Gain restored to 100%. This proves direct HDMI acoustic
output at the test location, not Miracast transport or end-to-end latency.
Local evidence: /mnt/entwicklung/tmp/profile-g-live-20260928/mic-hdmi-direct.pcm
and mic-hdmi-test.py. Recordings are not committed.

CORRECTION after detailed NetworkManager audit: the 13:07 WAIT_SOCKET attempt
selected Samsung S90CA 55, not ROCK. Fixed UI coordinates selected the wrong
row. It must not be used as a ROCK regression result. See
FIRMWARE-COMPARISON-20260928.md. Recovery checks and direct acoustic proof remain
valid independently of that receiver selection error.

Launcher requirement: run the Python launcher in a Type=oneshot service with
RemainAfterExit=yes, so systemd does not kill its container descendants when
the launcher exits. For target selection, mouse injection is not reliable in
this GNOME/XWayland environment. Visually verified keyboard selection and an
immediate NetworkManager peer-address check selected the correct ROCK in the
13:26:50 retry. Do not reuse run-audio-safe.py's fixed-coordinate click.

## GNOME sender latency diagnostic (2026-09-28)

GNOME Network Displays 0.99.0 sets a fixed 500 ms pipeline latency in
`src/wfd/wfd-media-factory.c`. `gnd-latency-probe.c` is an **opt-in diagnostic**:
it intercepts only a request of exactly 500 ms and applies 50 ms to that request.
Other values pass through. It logs requested/applied values. It is not installed
in the receiver image or enabled globally, and is not a general encoder policy.
The live test used Intel `vah264enc`; slower software encoders need separate tests.

Build into a temporary directory with:

```sh
gcc -shared -fPIC -Wall -Wextra -Werror -o /tmp/gnd-latency-probe.so experiments/profile-g/live-test/gnd-latency-probe.c -ldl
LD_PRELOAD=/tmp/gnd-latency-probe.so gnome-network-displays
```

Apply only to this sender process, never export LD_PRELOAD globally. Closing it
restores normal behavior; the installed executable is unchanged. A distributable
sender fix should use a configurable upstream source patch and encoder-specific
validation, rather than shipping this diagnostic interposer.

Receiver keeps configured RTP jitter buffering, sets additional tsdemux latency
to zero, and sets the optional Pulse sink async=false to avoid absent-audio
preroll blocking video. Pulse buffering is 40 ms rather than its default 200 ms.
The remaining delayed audio pad warning is **not** an audio success; dynamic
track detection and verified sound output remain outstanding.
