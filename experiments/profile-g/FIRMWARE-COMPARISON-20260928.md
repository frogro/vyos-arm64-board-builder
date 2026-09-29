# Firmware and successful-stream comparison

## Correction: 13:07 run selected the wrong receiver

NetworkManager at 13:07:44 activated peer E2:03:6B:D4:AF:DC. Discovery maps
that address to Samsung S90CA 55, not VyOS-TV. The automation used fixed window
coordinates (230,165); the discovery list changed. WAIT_SOCKET was therefore
not proof of a ROCK connection. At 13:07:56 GNOME requested disconnection.
No new firmware assertion appears in the 13:06–13:09 kernel interval; only
`No remain on channel event` at 13:08:51, after the failed attempt.
The later manual click did not produce a verified replacement ROCK session.

## Earlier actual ROCK stream

At 09:56:20 sender activated B4:8C:9D:A5:01:B7; the receiver's backup base MAC
is B6:8C:9D:A5:01:B0 (do not infer P2P peer identity from base MAC alone).
Independent ROCK log confirms GO negotiation, group formation on 2412 MHz,
ROCK as P2P client and ThinkPad 1C:1B:B5:43:3D:08 as group owner. Receiver
pipeline entered PLAYING. Sender IP activation completed 09:56:26, client
socket arrived 09:56:31, RTSP negotiation completed and STREAMING began
09:56:33, 1920x1080 at 30 fps. Audio delayed-link warning remained unresolved.
This is evidence of a stream connection, not proof of decoded/displayed frames.
Manual receiver-side PBC connection to the known ThinkPad was part of this run.

## Firmware

ThinkPad Intel 8265, kernel 7.0.0-31-generic, iwlmvm,
firmware 36.c8e8e144.0 (8265-36.ucode).
Two assertions at 09:57:06 and 09:57:12: 0x0000101F ADVANCED_SYSASSERT,
with NMI_INTERRUPT_LMAC_FATAL. First restart followed by second assertion,
interface recreation and sender error at 09:57:13. Both infrastructure WLAN
and P2P aggregation teardown report errors. This is a real firmware failure,
not merely a receiver timeout. Precise internal assertion cause is not decoded.

The card advertises managed + P2P + P2P-device with up to two channels, so
concurrent roles are supported in principle. Actual P2P was 2.4 GHz; managed
connection and reconnection were active concurrently. Multi-role/channel
scheduling or recovery is a hypothesis, not an identified defect or proven patch.
Current module power_save=N, iwlmvm power_scheme=2; not enough evidence to blame
power management. apt-cache currently offers the installed linux-firmware
20260319.git217ca6e4.1ubuntu. No firmware/module/kernel changes made.

Upstream Intel commit c7f676e3c800d2563ee98744bf3fbcbeecc247e9 (2025-05-28)
introduced c8e8e144 for 8000C/8265, replacing ca7b901d. No exact matching
public fix was identified in this investigation. An old firmware rollback is
not justified merely by a matching adapter name in unrelated reports.

Sources:
- https://kernel.googlesource.com/pub/scm/linux/kernel/git/iwlwifi/linux-firmware/+/c7f676e3c800d2563ee98744bf3fbcbeecc247e9
- https://wireless.docs.kernel.org/en/latest/en/users/drivers/iwlwifi.html
- https://wireless.docs.kernel.org/en/latest/en/users/drivers/iwlwifi/debugging.html

## Next valid comparison

Replace coordinate-based selection with exact named target selection and verify
NetworkManager's activated peer against the currently discovered ROCK P2P MAC
before accepting any test result. Retain host and client recovery timers.
Collect P2P group role/channel, IP activation, RTSP connection and PLAYING from
both ends. Only then compare firmware behavior; preferably use wired client
management so a WLAN reset does not interrupt evidence collection.

## Verified retry at 13:26:50

Mouse coordinate injection still selected an unintended peer despite a window
screenshot. That attempt was aborted on peer-address mismatch. Keyboard End +
Return after visually confirming VyOS-TV selected produced the correct
NetworkManager activation B4:8C:9D:A5:01:B7 at 13:26:50.

Receiver negotiated P2P client on 2412 MHz with the known ThinkPad as GO;
WPS-SUCCESS and GROUP-FORMATION-SUCCESS were followed by group teardown. Crucial
sender cause at 13:27:01: NetworkManager says `Peer requested in connection is
missing for too long, failing connection` and fails with `peer-not-found`.
It then tears down the GO group; receiver reports FORMATION_FAILED. Thus the
receiver's EAP failure alone must not be treated as proof of wrong credentials.
No new Microcode SW error was logged during this retry. Homebase also lost
beacons and reassociated (5/2.4 GHz roaming observed). This is evidence for a
peer tracking/radio coexistence investigation, not yet its root cause.

ROCK AP and kiosk were recovered and checked active. The revised start service
must use Type=oneshot and RemainAfterExit=yes: a default transient service
terminated its container when the short launcher exited in an earlier attempt.
No firmware or driver was changed. Stream/audio/latency remain unverified for
this retry. Raw receiver log kept locally mode 0600; do not commit credentials.

## LAN management / P2P-only retry

User connected ThinkPad Ethernet. Verified enp0s31f6=192.168.178.84 and route
to ROCK via Ethernet; disconnected infrastructure wlan0-equivalent wlp3s0
using NetworkManager (radio remained enabled). Only the P2P connection was
active on Wi-Fi during the successful connection.

At 16:39:58 NetworkManager activated correct peer B4:8C:9D:A5:01:B7.
At 16:40:28 sender got client socket; at 16:40:29 reported STREAMING with
1920x1080@30. ROCK logs WPS-SUCCESS, group started as client on 2412 MHz,
and pipeline PLAYING. This reproduces connection establishment with no
simultaneous infrastructure Wi-Fi connection. It does not yet prove a unique
root cause of prior failures or long-term stability. Audio queue1 delayed-link
warning remains, so no Miracast audio success is claimed.

Receiver recovery timer fired at 16:41:34 and verified AP/kiosk restored at
16:41:35; sender error followed at 16:41:39. About 65 seconds elapsed between
STREAMING and controlled receiver stop, with no new iwlwifi/Microcode error
in the inspected interval. This exceeds the roughly 33 seconds before the
morning firmware assertion, but remains a short test. Sender stopped and
homebase restored after test; management route remains Ethernet.

## USB adapter discovery check

Added ThinkPad USB 0e8d:7612 MT7612U, mt76x2u, interface wlx00c0cab95d25.
Kernel advertises P2P-client/P2P-GO (single-channel combinations), but no
P2P-device interface mode. GNOME created a provider for its NetworkManager
P2P device while Intel was temporarily unmanaged. No sinks appeared in this
bounded trial. Direct wpa_cli p2p_find returned FAIL; get_capability modes
returned IBSS AP MESH, with no P2P. This identifies a current discovery-stack
limitation, not proof the hardware can never support Wi-Fi Direct. No driver
patch was applied. Receiver restored; Intel managed/homebase restored; LAN
remained active. No USB Miracast stream/audio/latency success claimed.

## BrosTrend check

User-requested USB adapter 0bda:c811, wlx7419f81713f6, rtw88_8821cu.
Kernel advertised IBSS/managed/AP/AP-VLAN/monitor, no P2P modes. NetworkManager
exposes no P2P device for this adapter. With Intel temporarily unmanaged,
GNOME Network Displays sees only the unavailable Intel placeholder and creates
no BrosTrend P2P provider. Therefore no GNOME Miracast session can be tested
through this adapter in the current stack.

Unlike MT7612U, direct wpa_cli p2p_find returned OK and p2p_peers listed a TV
and printer. Thus it would be inaccurate to claim discovery is universally
impossible or the hardware is defective. The verified blocker is exposure
through the current driver/NetworkManager/GNOME path. Direct scan stopped;
sender stopped; Intel management/homebase restored; Ethernet route retained.
No kernel/driver patch, reboot or alternative vendor driver installed.

### BrosTrend repeat with confirmed active ROCK receiver

At 16:55 the ROCK receiver was running. With Intel unmanaged, BrosTrend direct
p2p_find returned FAIL (also after cycling only its NM managed state), and
GNOME had no usable provider. After enabling Intel again, the same control
command returned OK and GNOME explicitly created p2p-dev-wlp3s0 provider;
VyOS-TV B4:8C:9D:A5:01:B7 appeared at 16:55:47 while ROCK remained running.
Therefore the earlier OK/peer list with Intel enabled cannot be attributed to
independent BrosTrend operation. The isolated BrosTrend path did not discover
ROCK; Intel control discovered it within seconds. Both test sides cleaned up,
AP/kiosk active and homebase restored. No BrosTrend stream established.

## Alfa repeat and sender assertion

MT7612U reattached as phy4/wlx00c0cab95d25. ROCK receiver was explicitly
verified running throughout discovery. Intel temporarily unmanaged. Initial
GNOME 0.99.0 launch aborted at 16:57:31 in libpulse socket-client.c:170,
assertion c->defer_event == e, before discovery. No simultaneous firmware
crash observed. Restart with explicit PULSE_SERVER=unix:/run/user/1000/pulse/native
ran and created the Alfa provider, but discovered no sinks. This single restart
does not prove the environment variable fixes the libpulse bug.

Direct p2p_find initially FAIL; after cycling Alfa NM managed state returned
OK once, later FAIL again, no verified peers. Intel re-enabled at 16:59:19
created another provider but ALSO found no sinks in this same process before
17:00:12. Therefore this repeat lacks a successful simultaneous positive
control: do not conclude Alfa-only incompatibility from it. Device discovery
state after adapter switching needs a fresh isolated test. Receiver was stopped
via recovery, AP/kiosk verified active, sender stopped, homebase restored.

## Final older Alfa MT7610U test (17:07–17:09)

Different adapter: USB 0e8d:7610, mt76x0u, wlx00c0caae67bc (phy5).
Kernel advertises P2P-client/GO; NetworkManager creates its P2P device.
LAN management confirmed; Intel unmanaged throughout discovery and connection.
Fresh GNOME process with explicit Pulse server; ROCK receiver active, recovery
armed on both hosts. VyOS-TV discovered at 17:07:16, seven seconds after sender
startup, and ROCK independently discovered the Alfa MAC. Discovery therefore
works with this adapter without Intel assistance.

After remote-input portal approval, activation at 17:08:14 explicitly targeted
B4:8C:9D:A5:01:B7 via the Alfa. A duplicate start assertion was logged during UI
activation; the initial connection proceeded to WAIT_SOCKET. Receiver PBC was
requested, but no completed P2P group/RTSP stream was observed. NetworkManager
reported supplicant-timeout after 45 seconds (17:08:59). GNOME then crashed with
SIGSEGV in libgio at 17:09:01. No WLAN firmware crash observed in this interval.
Thus discovery passes, streaming does not; this does not establish hardware
incompatibility or isolate the negotiation failure from sender software state.
No audio or latency measurement possible. Recovery verified AP and kiosk active,
receiver stopped, ThinkPad homebase restored and LAN still connected.

## Intel-only final control (17:15–17:19)

Alfa unmanaged; management over Ethernet, Intel disconnected from homebase.
First GNOME start again aborted in libpulse (17:15:57), proving explicit
PULSE_SERVER is not a fix. Restart ran but initial discovery remained empty;
p2p_find returned FAIL. Removed the leftover Alfa P2P virtual interface,
restarted wpa_supplicant and cycled Intel management, then launched a fresh
sender. This combined cleanup does not isolate which stale state caused failure.

Correct VyOS-TV target B4:8C:9D:A5:01:B7 activated through p2p-dev-wlp3s0 at
17:17:07. Receiver PBC approved for Intel 1c:1b:b5:43:3d:08. NetworkManager
activated at 17:17:32, RTSP negotiated 1920x1080@30, STREAMING at 17:17:38.
ROCK logs show actual H.264 parsed caps, v4l2slh264dec NV12 output and
waylandsink input caps; receiver peer connected. Intel GO channel 1/2412 MHz;
station counters during stream: 42,139,485 transmitted bytes, 30,185 packets,
84 retries, zero tx failures, -32 dBm, 130 Mbit/s link rate. No observed Intel
firmware error. Connection continued until deliberate recovery around 17:19:10
(approximately 90 seconds); no preceding stream error observed.

This confirms transport and hardware video decoding again, not measured display
FPS or physical visible output: user did not know which screen to inspect and
was told it is the HDMI display attached to ROCK. Audio still fails delayed
linking from demux to queue1, so no audio/latency approval. All recovery verified:
ROCK AP/kiosk active, receiver stopped, ThinkPad homebase and LAN connected,
Alfa returned to managed/disconnected. No main changes.

## Powered-display visual test (17:31–17:36)

User powered the previously battery-empty ROCK display. Prior kiosk interruption
at 17:30:55 is explicitly logged by vyos-kiosk-reconcile-inputs: refreshed USB
event mappings and restarted container. This was not a logged kiosk crash.
Intel-only setup, Alfa unmanaged, Ethernet management. Stream at 17:32:31 with
H.264 hardware decoder/Wayland caps. User confirmed visible but frozen image.
Data continued (31.8 MB transmitted, zero tx failures in snapshot), keepalives
continued. Receiver audio demux delayed-link failure persisted.

Diagnostic comparison: backed up mounted miracle-player-probe.py and temporarily
forced pipeline(..., False, ...) to omit its audio branch, then started a fresh
receiver/sender session. Stream at 17:35:25; user confirmed picture updates but
large latency, including cursor. This supports audio preroll/blocking as a
candidate explanation for the initial freeze; repeated A/B and frame timing are
still required. Video-only does not solve latency. No measured FPS/latency claim.
Kernel logs include hdmi-audio-codec.8.auto Unknown ELD version 0 and ASoC -19;
ALSA HDMI0 identifies RTK FHD HDR, HDMI1 monitor name empty. Do not equate these
probing errors with a proven cause of video latency. Audio remains unverified.

Restored the probe player from backup after test, AP/kiosk active, homebase and
LAN restored. This supersedes any interpretation of STREAMING/caps alone as
full functional approval: visible moving video now confirmed, but latency and
audio remain blockers. No main or image change.

## Latency optimization and user-confirmed comparison (17:41–17:49)

Installed receiver gst-inspect confirms tsdemux default latency=700 ms. First
comparison removed this extra latency (latency=0), retained RTP jitter=50 ms,
and omitted audio. Intel stream 17:41:58; user reported clearly faster picture,
then clarified that both typing and cursor still lagged (not missing input).

GNOME 0.99.0 source independently confirms fixed gst_pipeline_set_latency(500 ms):
https://github.com/GNOME/gnome-network-displays/blob/0.99.0/src/wfd/wfd-media-factory.c
A process-local diagnostic interposer changed only that exact request to 50 ms,
with runtime log confirmation at 17:47:54. No installed executable replaced.
Receiver also enabled optional audio with async=false, explicit H264/AAC pad
filters, 40 ms Pulse buffer/10 ms write latency. User confirmed again:
"Nochmals deutlich schneller, Bild bewegt sich". Thus absent-audio no longer
froze the picture in this test. AAC negotiation was logged but demux audio pad
link still failed: audible audio remains unverified. No objective end-to-end
latency measurement or 60-fps claim; negotiated format remains 1080p30.

Intermediate audio-safe reconnect at 17:45 established P2P but never reached
RTSP. After bounded cleanup and fresh supplicant, next stream succeeded. Do not
count that intermediate connection as a passed audio test.

Receiver changes are in profile-g/container/miracle-player.py; sender probe is
in live-test/gnd-latency-probe.c with reproduction/limitations. Twenty tests pass,
including actual GStreamer live-video handoffs while an optional audio source
supplies no preroll data. Restored AP/kiosk/homebase/LAN and stopped diagnostic
sender; optimized receiver player remains staged for next G test. No main change.

## HDMI audio selection fix (17:53 onward)

New G-specific hdmi-audio.py selects the audio device matching the active DRM
output EDID/ELD and starts Pulse without probing all sound cards. Actual mapping
HDMI-A-1 -> plughw:1,0 -> sink g_hdmi, stereo 48 kHz; unused HDMI1 not opened.
Since 17:53, zero new hdmi-audio-codec/ASoC kernel errors observed through active
stream at 17:57:41. Local 660 Hz/0.5-second tone played through Pulse g_hdmi;
user confirmed hearing it. This confirms output selection/playback, not Miracast
AAC delivery. Audio demux delayed linking remains in the received stream.

First connection attempts after change failed P2P scan/formation with ret=-22,
supplicant-timeout; not counted as video passes. Fresh bounded restart of both
ends yielded STREAMING at 17:57:41, with 50 ms sender diagnostic still active.
21 automated tests pass, including EDID/ELD selection under card renumbering,
disconnect/no-capability/ambiguous matches and absent-audio preroll regression.
Physical second-port and unplug/replug tests not performed.

At 17:59:09 stream remained active, g_hdmi remained default, and new HDMI codec
error count remained zero. User had confirmed the local tone; renewed visual
confirmation was still pending at cleanup. Restored AP/kiosk/homebase/LAN and
stopped process-local sender diagnostic. Final HDMI module staged for next run.
