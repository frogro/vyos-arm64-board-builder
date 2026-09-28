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
