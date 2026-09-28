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
