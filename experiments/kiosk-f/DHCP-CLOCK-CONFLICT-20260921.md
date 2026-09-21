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

Kea vendor unit has After=time-sync.target, but VyOS override resets After=
and sets After=vyos-router.service. chrony-wait.service is disabled/inactive;
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
