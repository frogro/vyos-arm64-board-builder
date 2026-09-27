# Moonlight over native WireGuard — 2026-09-28

External mobile-network test on ThinkPad via IPv6-capable Samsung hotspot; Ethernet disconnected. Native VyOS wg27 configured with configure/set/commit, dedicated inner addresses 10.203.27.1/30 and 10.203.27.2/30. Moonlight explicitly uses 10.203.27.1; route inspection confirms wg27, and WireGuard counters increase during stream. The encrypted outer endpoint is ROCK global IPv6, UDP 51829 permitted by FRITZ!Box. Tailscale only supplies a separate management/rollback channel.

Runtime: existing normal Wayland kiosk temporarily switched to native-remote-20260927 overlay with tested Sunshine GPU/RGA rotation, MPP hardware encoding, input bridge, PulseAudio and isolated prior paired test state. Sunshine runs as kiosk user. Streaming uses temporary host networking; this does not establish native bridged Sunshine configuration, although routed bridge ping/HTTP was separately verified.

HEVC: 1080x1920, 60 FPS target, 2 Mbps, client hardware decoding, absolute mouse, frame pacing/vsync disabled. User explicitly confirmed upright image, mouse/clicks and audible test tone. Server direct RGA frame counts advance at approximately 60 FPS. A bounded client timeout and independent host rollback timer were armed.

No lasting native config save, main change, reboot or production pairing replacement. Measurements and cleanup verification are recorded below. This is short functional acceptance, not a long-duration test or a general mobile latency guarantee.

## Completed short comparisons

Both codecs tested over 4G (user confirmed), 1080x1920 at target 60 FPS and 2 Mbps.

| Metric | H.265/HEVC | H.264 |
|---|---:|---:|
| Incoming FPS | 59.98 | 60.24 |
| Rendered FPS | 59.75 | 59.50 |
| Host processing average | 13.0 ms | 12.9 ms |
| Host processing min/max | 9.6 / 213.7 ms | 9.6 / 49.7 ms |
| Network latency average | 43 ms | 49 ms |
| Network-reported variance | 8 ms | 6 ms |
| Frames dropped by connection | 0.27% | 0.00% |
| Frames dropped due to jitter | 0.34% | 0.91% |

User explicitly confirmed image orientation, mouse/clicks and test tone for BOTH codecs. Client runs bounded at 85 seconds (HEVC) and 45 seconds (H264), including startup. Different short time windows and mobile fluctuations do not establish one codec as superior. RTT/host metrics are not an end-to-end input latency measurement. Ended by planned timeout, not decoder failure. Temporary host-network integration was used; no permanent bridge exposure or durable CLI configuration change is inferred.

## Cleanup verified

Normal kiosk service is active again with `localhost/vyarm-kiosk:github-36339240710`. RGA experimental_full_csc returned to `N`. Both temporary wg27 interfaces are absent; temporary global IPv6 addresses on ROCK eth0 are removed. Independent rollback timer is inactive after restoration. The temporary client key copy in /etc/wireguard was removed; private working credentials are not part of this document or commit. The user-managed FRITZ!Box IPv6 UDP 51829 permission remains configured.
