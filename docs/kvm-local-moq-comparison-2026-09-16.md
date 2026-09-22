# Local MoQ / WebRTC comparison, 2026-09-16

## Scope

ROCK 5B 999.202609151917, MediaMTX v1.20.0. LAN only: server
192.168.178.173, browser host 192.168.178.78. No Tailscale test, firewall
changes, backend switch or firmware installation in this comparison.
The existing FFmpeg Rockchip pipeline publishes one H.264 1920x1080 stream
reporting 60 fps to local RTSP. Network measurements do not verify displayed fps.

The user confirmed MoQ playback in Firefox after MediaMTX was restarted with
correct system time. The prior boot used an April date; MediaMTX's WebTransport
certificate is created at startup for 14 days. A large subsequent clock change
can therefore leave an expired certificate in memory. Restarting generated a new
fingerprint and the server then logged the browser reading `kvm` over MoQ.
Permanent recovery from incorrect boot time remains unresolved.

## Method and limits

Read UDP header counters on eth0 for this single browser host, filtered to ports
8189 and 8892. Record process CPU deltas and resident memory from /proc. Observe
session logs. No video or packet payload recordings are saved.

Both WebRTC and MoQ were observed transmitting concurrently to the same host.
This permits comparison of network volume for the same encoder output, but
not isolated per-protocol CPU cost. Background browser tabs may render at a
different rate; server traffic is not evidence of equivalent displayed frames.
The requested moving-window pattern has not been independently verified.

Earlier 30-second MoQ observation: 1.588 Mbit/s outgoing UDP payload, 0.019 Mbit/s
incoming; MediaMTX 9.22% of one core, 63.46 MiB RSS. LAN ICMP RTT (20 probes):
minimum 1.924 ms, mean 3.936 ms, maximum 6.041 ms, no lost probes. ICMP RTT is
not video latency and does not establish zero QUIC packet loss.

## Proposed CLI behavior (not implemented)

Keep capture `backend` separate from delivery protocol. A possible future leaf
is `set service kvm-over-ip video transport webrtc|moq|both`; this syntax is a
proposal, not an available command. Apply it only to the FFmpeg/GStreamer paths
using MediaMTX. uStreamer keeps its MJPEG transport and must reject incompatible
explicit transport selections.

Prefer WebRTC as a conservative default pending broader MoQ validation. Explicitly
generate `webrtc` and `moq` booleans so dependency defaults cannot silently expose
an additional protocol. In single-protocol mode, stop the unused listener(s),
rather than generating hidden firewall rules. `both` is an intentional option
for sites that need both. Listening address and all transport ports must be
consistent and documented, including IPv6 behavior.

For MediaMTX 1.20.0, MoQ starts both browser HTTP2/HTTP3 and native QUIC listeners.
Do not assume native UDP 8893 can be disabled independently without testing the
version's configuration handling. The browser test uses TCP/UDP 8892, while
WebRTC uses TCP 8889 and UDP 8189. Internal RTSP remains loopback-only.

The administrator continues to own native VyOS firewall and tailnet access
policy. Offering both transports is possible but increases the endpoints to
maintain and test; neither option creates viewer-versus-controller roles.

## Required before a performance conclusion

Measure client-rendered fps/dropped frames and true capture-to-display latency
with a repeatable source/time reference. Compare foreground browser sessions
sequentially for isolated CPU costs. Resolve time/certificate behavior and test
supported browsers before choosing MoQ as a default. No lower-latency claim is
established by bandwidth measurements alone.

Sources:
- https://github.com/bluenviron/mediamtx/blob/v1.20.0/internal/protocols/httpp3/server.go
- https://github.com/bluenviron/mediamtx/blob/v1.20.0/internal/servers/moq/server.go

## Concurrent measurement result

Second 40.03-second sample: exactly one UDP flow per transport in each direction
between the server and the same browser host.

| Metric | WebRTC | MoQ |
| --- | --- | --- |
| Outgoing UDP payload | 2.397 Mbit/s | 2.253 Mbit/s |
| Incoming UDP payload | 0.003 Mbit/s | 0.021 Mbit/s |
| Outgoing UDP datagrams | 11,719 | 9,868 |
| Session disconnects in sample logs | None | None |

MoQ's outgoing volume was about 6% lower in this sample; this is not an image
quality or latency result. Every sampled wall-clock second included packets
for both protocols. tcpdump reported no kernel capture drops (not proof of no
network loss).

Combined MediaMTX: 10.22% of one CPU core and 62.84 MiB RSS. Shared encoder:
269.16% of one CPU core (about 2.69 cores) and 70.73 MiB RSS. The encoder cost
cannot be assigned to either output protocol. No protocol was disabled or
selected as a new default as a result of this measurement.

## Reboot verification after set-locales.sh

A user-authorized warm reboot was performed at approximately 02:05 CEST.
Boot ID changed from `24ea9144-3fae-4e4b-a7fd-b894701d3186` to
`f11d6544-39c7-4a56-8c57-48ecbfc860d8`.

Before reboot, timedatectl reported synchronized system time, active NTP,
Europe/Berlin, and UTC RTC. Reading rtc0 (hym8563) returned the correct date.
Nevertheless, the new boot's kernel log at monotonic +2.49 seconds explicitly
reported setting the clock from RTC to `2025-04-09T22:10:43 UTC`. Chrony started
at +44.87 seconds and stepped the clock by 12,197,855.63 seconds at +50.50.
The discrepancy between the kernel date and subsequent April 2026 service
start timestamps indicates further early-boot clock adjustment; root cause
has not been established. Do not conclude the battery is faulty from this test.

MediaMTX's own startup logs had the corrected September date. Both protocols
subscribed successfully. MoQ initially disconnected at 02:07:14 with
`network is unreachable`; a new local browser session subscribed successfully
at 02:07:47. No manual service restart was performed after this boot. Both KVM
services remained active with NRestarts=0. ffprobe found H.264 1920x1080 with
reported 60 fps. Tailscale returned Running with unchanged addresses and an
empty Health list; systemd reported no failed units.

Result: automatic service recovery and post-reboot MoQ subscription passed,
but correct time from the beginning of boot failed. set-locales.sh/NTP alone
has not proven to solve RTC/boot time retention or prevent the certificate
race. Cold power removal/battery retention was not tested. The user confirmed the local MoQ picture returned after reloading the page.

## Implementation follow-up

The transport selection and Chrony-gated MediaMTX supervisor are now included
in the pending build. Earlier statements above describe the pre-fix test image.
Unit tests cover protocol configuration and clock-state decisions; the new
image still needs cold-boot, delayed-NTP and browser recovery acceptance.
