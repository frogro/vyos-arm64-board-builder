# Modem setup persistence and lifecycle

`modem-connect.sh` retains the universal USB/PCIe detection, backend selection,
FCC unlock, AP/WWAN NAT, wired preference and modem recovery implementation.
It remains an administrator setup assistant, not a new native VyOS CLI node.
During manual setup, `--backend auto` and `auto-native` first try the existing
VyOS `interfaces wwan` configuration when a suitable ModemManager interface is
available. `--backend vyos` requires this handover; `--backend mm` explicitly
selects the older helper-managed ModemManager backend.

The native path writes APN, DHCP and default-route distance through
configure/commit/save. It verifies the DHCP service, address and bound data
path before accepting the handover. It never persists a modem-assigned IP or
gateway in config.boot. If the attempt fails, its interface configuration is
rolled back before any fallback; an existing native owner is never silently
replaced by a competing helper.

Current VyOS maps `wwanN` to ModemManager modem index N. The assistant checks
this mapping and rejects a native handover if it does not match. This is a
known upstream limitation, not a board-specific device-number assumption.

Image-owned code lives in `/usr/local/share/vyos-arm64-firstboot/`:
`modem-connect.sh`, `modem-services.sh` and `modem-native-wwan.sh`. Keep these files
together when deploying manually. User home entries are convenience links.

Settings and backend caches are now under `/config/modem-connect` (directory
0700, files 0600). Known legacy `/etc/modem-*.conf` files are copied there only
when no persistent counterpart exists. This migration must run **before** an
image update to preserve an existing legacy installation. It does not search
old images or execute their scripts. Normal VyOS configuration-copy during
image installation must include this `/config` state.

`vyos-modem-restore.service` runs at boot. Without saved modem configuration it
does nothing. With helper-managed configuration it recreates units and the
failover monitor from the current image and queues modem-connect. With
`MANAGEMENT=vyos`, it removes the old dialer/failover/unlock services and creates
only `vyos-modem-hardware.service`. That helper prepares/discovers hardware and
uses the existing VyOS `connect interface` command; it does not own APN, IP
configuration or a parallel reconnection loop. VyOS's existing five-minute
WWAN cron job handles periodic redial.
The dependency chain is connect -> failover, with unlock before connect only
when the saved modem requires it. A saved `UNLOCK_KIND=none` removes the unlock
unit and dependency. Boot execution waits for the `/config` mount and completed
VyOS initialization; `After=vyos-router.service` alone is insufficient because
that service is Type=simple. USB recovery rules are
recreated when the FM350 is detected. No modem setup is automatically applied
on a new unconfigured installation.

Transport policy (`auto`, `usb`, `pcie`) is saved separately from the detected
transport. Old configurations use their saved transport as a migration default.
Auto still prefers PCIe when both FM350 transports are present. ModemManager
selection is restricted to the chosen physical FM350 and explicit transport.

FCC success markers and native QMI/MBIM session handles are under `/run`, not
persistent storage. A marker is not proof that the modem is still unlocked:
the modem is queried again before reusing success. Failed unlock must not let
the unlock service succeed. `--probe` is now inventory-only and does not run
unlock, stop services, rewrite rules or configure networking.

The route cache remains persistent because it records the prior VyOS static
next-hop to remove when a gateway changes. It is not proof of connectivity;
normal setup and failover still validate current interfaces and the data path.

Manual setup replaces the previous modem settings and generated services.
Settings are archived under `/config/modem-connect/previous-*`; these backups
are never loaded automatically. Boot, recovery and diagnostic unlock runs do
not perform this reset. The prior next-hop journal is retained until routing
replacement removes the old modem route. LAN/AP/Tailscale/KVM remain outside
this reset.

If no ModemManager modem appears after the discovery timeout, a single known
SDX55 PCI device (`17cb:0306`, bound to `mhi-pci-generic`) can be rebound once
per invocation. This is skipped for USB selection, FM350 selection, multiple
candidates, exposed ModemManager devices and `--no-auto-repair`. The existing
post-discovery recovery remains unchanged.

## Validation, 2026-09-16

- Shell lifecycle tests: USB/PCIe/auto selection, stale/failed unlock markers,
  image-owned service generation and inventory without service mutations.
- Rootfs packaging tests include companion library and restore service.
- ROCK USB FM350 `0e8d:7127`: real FCC unlock succeeded; repeat unlock succeeded.
- Internet data-path test blocked on image 999.202609160043: its kernel has
  `CONFIG_USB_NET_RNDIS_HOST` unset. Network profile now requests the driver.
- ROCK PCIe Quectel RM505Q-AE: MHI control/MBIM/network drivers present;
  ModemManager connected with APN `internet`, no FCC unlock. Interface-bound
  Internet ping succeeded (3/3), Ethernet metric 20 and WWAN fallback metric 200.
  Initial modem discovery needed one targeted MHI device unbind/rebind; this
  is a test intervention, not proof of unattended startup.
- Native Quectel WWAN: successful DHCP lease, interface-bound Internet ping
  (3/3), and reconnect through the native operational command after deliberate
  disconnect. Repeated manual setup successfully replaced its previous state.
  The old helper dialer, failover monitor and unlock service are absent.
- Native scheduled redial verified: manual disconnect at 10:57:44, still
  disconnected at 10:59:49; unchanged `/etc/cron.d/vyos-wwan` ran at 11:00:01
  and completed at 11:00:06. Modem connected again, 3/3 bound Internet pings.
  No manual reconnect command or custom watchdog was used during this test.
- Initial reboot exposed a `/config` readiness race. This was corrected by
  waiting for completed VyOS initialization. A following recovery exposed a
  queued netlink DOWN event stopping DHCP after MHI device recreation. The helper
  now brings the link up and, if DHCP remains inactive, reapplies the existing
  native WWAN configuration once through `interfaces_wwan.py`.
- Final warm reboot (boot ID `66905f8a-6812-4334-a949-baa1b06335e8`):
  unattended native Quectel connectivity verified at 11:09:39; DHCP lease and
  3/3 interface-bound Internet pings confirmed. No manual reset or power cycle.
  No MHI/IOMMU fault in this boot. This does not prove cold-boot behavior or
  that every modem firmware hang can be recovered without removing power.
- Installed image lacks `mbimcli` (`libmbim-utils`), despite the MBIM shared
  libraries being present. The network profile now installs explicit userspace
  dependencies and rejects incomplete common USB modem payloads.

Existing limitations retained: FM350 USB handling temporarily/exclusively uses
ModemManager masking as before; concurrent independent ModemManager-managed
modems are not validated. Thunderbolt auto-authorization and legacy eth1
recovery assumptions are unchanged. They need separate policy/multi-device
work, not an untested replacement during this persistence fix.
