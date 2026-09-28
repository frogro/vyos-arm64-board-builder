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
