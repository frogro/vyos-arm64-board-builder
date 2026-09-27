# ROCK live acceptance — 2026-09-27

Image: 999.202609250800 from corrected GitHub run 36314140176.
Runtime: localhost/vyarm-kiosk:wayland-user-20260926; kernel 6.18.50-vyos.

## User-confirmed and intentionally deferred

The user confirmed display, touch and cold-start recovery. A second kiosk start
was visible after cold boot. Decoder endurance and fresh SD installation were
explicitly deferred. No fresh-install acceptance is claimed.

## Configuration backup and final state

Private local backup: /mnt/entwicklung/Documents/Codex/2026-09-13/vy/work/acceptance-20260927/
Contains config.boot, settings.tar.gz, SHA256SUMS and RESTORE.md. Credentials and
backup contents are not committed. Restoration instructions select persistent
configuration/state rather than restoring stale DHCP runtime data wholesale.

Tests used temporary native CLI commits without saving. At completion the
original saved and running configuration and Sunshine state were restored;
config.boot and original Sunshine files were compared with their backups.
Wayland, HDMI-1, rotation 90, automatic decoding and both buffer options remain
selected. Sunshine is disabled and no Profile-D service is configured, as before.
Temporary credentials were removed and the independent rollback timer stopped.
No failed systemd units remained. No matching decoder timeout, panic or IOMMU
fault was observed in the final checks.

## Profile D

Actual HDMI input at /dev/video0 reported 1920x1080 progressive approximately
60 Hz. The initial 30-fps request was rejected by capture-format validation;
subsequent tests used 60 fps.

- ustreamer: online, captured_fps 60; valid 1920x1080 MJPEG snapshot.
- FFmpeg: h264_rkmpp, NV12, approximately 60 fps and 8 Mbps; receiving the RTSP
  stream decoded 110 H.264 frames in the short two-second probe.
- GStreamer MPP: negotiated 1080p60 H.264 stream with limited range, BT.709
  matrix/primaries and IEC 61966-2-1 transfer metadata. A separate stream-copy
  sample requested 60 packets/frames but decoded only 20 frames on inspection.
  This is not a completed 60-fps playback qualification and needs investigation.

No physical HID/virtual-media interaction, browser WebRTC end-to-end test or
Profile-D HEVC qualification was performed in this acceptance pass.

## Sunshine and operating modes

Native CLI transitions between X11 and Wayland were exercised. Sunshine enable
under DRM Wayland was explicitly rejected by the current validation, requiring
X11. Under X11 Sunshine started, but encoder probing selected libx264 software;
the experimental MPP device path was not exposed by this deployed runtime.

Temporary credentials were set through the request operation. Authenticated
clients and pending operations returned empty lists through the native handler.
The additional op-wrapper PTY harness timed out for these queries; this alone
is not evidence of an interactive-user CLI defect. Actual Moonlight pairing,
streaming, input and audio were not validated.

Audio enabled/disabled and control/view-only CLI changes produced the expected
policy and Sunshine configuration. No reachable PulseAudio server was present
in the tested container, so audible remote audio is not confirmed.

Wayland software mode was additionally verified with actual H.264 playback:
FFmpegVideoDecoder, platform decoder false, 600 frames, 15 dropped, EOS at 10 s.
The accelerated-video-decode disabling flag was present. Original auto mode was
restored afterwards; endurance tests were not run.

## Additional restart finding

The cold-start log and several later CLI commits contain the input reconciler
message: refreshed configured USB event mappings and restarted container.
Even changes confined to Sunshine audio/input policy triggered another kiosk
restart. The remote-only predicate and mounted-policy detection both returned
true, so the restart avoidance for remote settings is undermined by subsequent
input reconciliation.

The generator and reconciler both retain stable input source paths. The
reconciler rebuilds selected AddDevice lines at the start of [Container] and
compares both generated text and Podman device mappings before restarting.
The exact text/order versus mapping mismatch still needs an isolated diff;
do not attribute this to a proven source-path canonicalization defect.
Next correction: make generation/reconciliation idempotent, retain hotplug
recovery, and verify policy-only commits do not restart the kiosk.

## Release limits

Full F approval remains pending the restart correction and intended Sunshine
capability decision (X11/software-only versus additional validated hardware and
audio support), real Moonlight tests, GStreamer receive-count investigation,
and the user-deferred fresh-install/endurance tests. Main was not changed.
