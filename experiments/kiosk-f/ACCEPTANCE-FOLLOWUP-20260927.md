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
