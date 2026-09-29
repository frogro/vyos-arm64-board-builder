# AP DHCP duplicate allocation after boot clock step

Read-only diagnosis 2026-09-21, prompted during NUC build migration.
No network configuration or lease mutation performed.

## Observed sequence

- ThinkPad DHCP client currently holds 10.3.141.51/24, MAC 1c:1b:b5:43:3d:07,
  from 10.3.141.50, lifetime 86400 seconds; NetworkManager method auto.
- Current boot Kea logs under Apr 27 21:49:45 show DHCPACK / lease allocation
  of .51 to that ThinkPad MAC for 86400 seconds.
- chronyd then reports clock wrong by 12677689.468955 seconds and steps forward
  to Sep 21 15:24:34. This puts the old server-side expiration in the past while
  the client still counts its relative lease lifetime.
- Kea cleanup at Sep 21 20:24:40 reports zero retained leases.
- Sep 21 21:23:31 Kea allocates .51 to nuc12wski5, MAC 78:af:08:68:9b:47.
- User disconnected NUC Wi-Fi before diagnosis. Only ThinkPad associated at check;
  ARP .51 is ThinkPad. NUC reachable over LAN 192.168.178.136, SSH auth pending.

Lease persistence IS enabled: memfile /config/dhcp/dhcp4-leases.csv.
The active file currently has only a header; rotated .2 contains NUC lease.
Do not infer lost persistence from reading only the active CSV.
Pool .51-.250, no shown reservations. Ping check false.

Correction after inspecting effective dependencies: the VyOS drop-in contains
an empty After= followed by After=vyos-router.service, but systemd dependency
lists cannot be cleared by an empty drop-in assignment. The effective Kea
After list still includes time-sync.target. chrony-wait.service is disabled/inactive;
time-sync.target was reached before the actual clock step. Merely restoring
After=time-sync.target does not establish an actual synchronization barrier.
Current chronyc tracking synchronized and RTC now gives correct date.
Kernel boot log had RTC set system clock to 2025-04-09; subsequent startup
already showed April 2026. Full early-clock transition not yet investigated.

## Follow-up

First migrate build using NUC LAN. Keep NUC off AP until lease conflict resolved.
Renew clients with a controlled reconnect after current time is valid, accounting
for this host's active remote/SSH access. Avoid arbitrary MAC-specific builder
reservations as the generic fix. Audit VyOS boot time initialization and design
bounded time readiness / persisted last-known time behavior for offline routers;
never make AP availability depend indefinitely on Internet NTP. Verify with a
controlled wrong-clock boot regression and two clients before enabling generally.

After NUC build handoff, both clients are on the home network and no station is
associated with ROCK AP. Kea still retains .51 for NUC. No simultaneous active
conflict observed now, but boot time-handling defect remains uncorrected. NTP
currently synchronized, D/F services active. No DHCP mutation or reboot done.


## Upstream comparison and proposed boot policy (22:36 local)

- OPEN CHECKPOINT: reproduce wrong RTC + delayed NTP + duplicate lease with
  an unmodified x86 VyOS image in an isolated VM. Deferred by user. No x86
  runtime reproduction has been performed.
- Upstream vyos/vyos-1x rolling e559637d34e0169905ecb1c6875e8a67b38d4678
  contains the same Kea drop-in and makestep 1.0 3 Chrony template. Package
  architectures are amd64 and arm64. Source comparison is not a runtime proof.
- Live effective ordering: vyos-router starts at monotonic 21.020 s,
  Chrony at 61.818 s and Kea at 62.946 s. Chrony's generated drop-in orders it
  AFTER vyos-router. Do not add a global wait-for-Chrony before vyos-router:
  that risks a startup dependency cycle.
- Proposed sequence: read RTC/persisted lower bound; configure router interfaces,
  routing, DNS and WAN; start Chrony; check real clock readiness; release DHCP
  only under an explicit clock policy. A monotonic bounded wait may expire but
  must not silently authorize a later large clock step with active leases.
- Trusted RTC can support offline operation, but a plausible date or saved lower
  bound alone does not prove RTC accuracy after an extended power-off.
- With unknown time, safest initial policy is to leave DHCP blocked and retain
  static management access. Fully offline DHCP requires a separately implemented
  no-step clock policy and a controlled transition to valid time. Not implemented.
  This availability tradeoff must be explicit; short leases or ping checks alone
  do not eliminate the problem.
- set-locales must not unconditionally restart Chrony or invoke makestep. A VyOS
  NTP commit may itself restart Chrony, so guarding only the last script lines
  is insufficient. No production configuration changed in this investigation.

## Live probe scope

Transient read-only online probe `chronyc waitsync 3 0.1 0 1` succeeded against
production Chrony (remaining correction about 79 microseconds). A missing command
socket returned failure immediately. These verify readiness/error handling, not
boot ordering or DHCP duplicate prevention. No clock change, DHCP restart or
reboot was performed.

A separate transient Chrony instance on the ROCK, with no sources, private network,
non-root _chrony user, empty capability set and -x (cannot control the clock),
reported Stratum 0 / Not synchronised. Its waitsync check failed after exactly
three attempts as intended. The first attempt to launch this non-root instance
failed with 'Not superuser'; adding documented -U fixed the harness. The isolated
instance and temporary config were removed. Production Chrony remained synchronized;
Kea and kiosk service remained active. No delayed-NTP transition or boot test yet.
