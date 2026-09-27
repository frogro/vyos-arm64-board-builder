# Native VyOS WireGuard live test, 2026-09-27

Status: local underlay verified; external hotspot test pending FRITZ!Box endpoint/UDP forwarding. No Tailscale transport is used by this tunnel.

## Configuration tested
Applied using `/bin/vbash`, `/opt/vyatta/etc/functions/script-template` and the native configuration session (`configure`, `set`, `commit`). Not saved to boot configuration. Dedicated test interface; no default route changes or firewall widening. A 20-minute independent rollback deletes only this test interface through native CLI. Interface names must be `wgN` (the initial `wgtest27` name was rejected without configuration changes).

```text
configure
set interfaces wireguard wg27 address '10.203.27.1/30'
set interfaces wireguard wg27 description 'Temporary native WireGuard acceptance test'
set interfaces wireguard wg27 port '51829'
set interfaces wireguard wg27 private-key '<SERVER_PRIVATE_KEY>'
set interfaces wireguard wg27 peer thinkpad public-key '<CLIENT_PUBLIC_KEY>'
set interfaces wireguard wg27 peer thinkpad allowed-ips '10.203.27.2/32'
commit
exit
```

Never paste literal placeholders. Keys generated separately and excluded from Git. No `save` during this temporary test.

ThinkPad tunnel address `10.203.27.2/30`, MTU 1380, server peer endpoint initially `192.168.178.173:51829`, keepalive 25. AllowedIPs only VyOS tunnel address and selected container /32. Linux client uses native wireguard-tools, not a VyOS command. Ubuntu AppArmor requires the root-owned private key at an allowed location under `/etc/wireguard/`; no AppArmor profile disabled.

## Observations

- Native VyOS configuration committed successfully; kernel WireGuard interface and peer created.
- Local UDP handshake and bidirectional counters confirmed on both machines.
- Three tunnel pings to VyOS: 0% loss, average 1.121 ms.
- Kiosk address changed after container recreation: previous 10.89.50.10 is absent; live inspected address 10.89.50.14 replies through WireGuard.
- Therefore a static stale container address must not be used as proof of VPN failure. Persistent deployment needs an explicitly configured stable container address or an appropriately routed subnet and discovery.
- Existing firewall permits test WireGuard ingress/forwarding; no blanket rule added. This is a property of this live configuration, not an assertion that every deployment has appropriate rules.

## External test prerequisite
FRITZ!Box UDP 51829 -> ROCK 192.168.178.173:51829. Need public reachable IPv4 or equivalent IPv6 topology; DS-Lite/CGNAT may prevent direct inbound IPv4. ThinkPad must disconnect both home LAN and ROCK Wi-Fi, then use Samsung hotspot. Switch peer endpoint to public address, verify a fresh handshake, route, TCP connection and streaming separately. Do not declare this passed from local results.

Cleanup uses `delete interfaces wireguard wg27` and `commit` on VyOS; remove temporary wg27 interface and test key from ThinkPad. Remove temporary FRITZ!Box forwarding if not retained for a planned deployment.

Additional local checks: SSH to VyOS at 10.203.27.1 returned the active kernel. A temporary, non-root, 120-second HTTP responder in kiosk returned `WG_CONTAINER_TCP_OK` through wg27 at 10.89.50.14:18089 (first immediate request raced startup; repeat succeeded). Container tunnel ping: 3/3 replies, mean 1.253 ms. ThinkPad cleanup timer also scheduled to remove only test wg27 and its root-owned key.

## IPv6 alternative prepared
FRITZ!Box screenshot shows WAN IPv4 in 100.64.0.0/10 shared address space; simple inbound IPv4 forwarding is insufficient. Public IPv6 prefix is present. ROCK initially had only link-local IPv6, accept_ra=0. Applied temporarily via native CLI:

```text
configure
set interfaces ethernet eth0 ipv6 address autoconf
commit
exit
```

This sets accept_ra=2 with forwarding still enabled. `rdisc6 -1 eth0` solicited an advertisement; a global EUI-64 address appeared. The client peer endpoint was changed to that ROCK global IPv6 address (not the FRITZ!Box WAN address); inner IPv4 tunnel ping still succeeds locally. Rollback script extended to delete this temporary autoconf option as well. External IPv6 test still requires UDP 51829 IPv6 firewall permission for the ROCK and IPv6 connectivity through the Samsung hotspot. Public addresses are deliberately omitted here; derive fresh values from live state.

## External hotspot result
ThinkPad LAN disconnected; Samsung hotspot assigned 10.174.69.115/24. Wi-Fi had only link-local IPv6 and no IPv6 default route. WireGuard retained the earlier local handshake; no fresh external handshake was observed. Thus native WireGuard local function is verified, external transport is blocked by this client's missing IPv6 connectivity while the home endpoint is behind provider IPv4 NAT. Do not label this an external WireGuard or Moonlight success. Requires an IPv6-capable external access network, a publicly reachable IPv4 home endpoint, or a separate reachable WireGuard relay/server topology. Tailscale is a distinct alternative already available, not proof of native direct reachability.
