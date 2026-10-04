# Profile E: print server — live prototype

E is reserved for independent CUPS printing and optional USB forwarding on all
supported boards, including E52C. The previously proposed remote-maintenance
profile moves to **H**. E does not require D/F/G. G may select the same shared
VirtualHere component; there must only be one server and one `service usb-server`
configuration, even with E+G.

This directory is the first ROCK live prototype, **not yet a release build
selector or an update-safe installation package**. Do not assume published
images contain it. No third-party VirtualHere binaries are distributed here.

## Architecture and current live CLI

CUPS/Gutenprint run in a Podman container; VirtualHere runs as a separate native
service. The generic official ARM64 VirtualHere build was downloaded directly
for the test (4.8.8, SHA256
`09deced5586ed37b8b3db7a6187d84029f65d487c3c2b24a949b993b3d582077`).
The Linux console client runs as a normal application, not as a licensed client
daemon. Only one USB device is shared. Proprietary software distribution remains
to be settled before including it in public images; prefer explicit on-demand
installation from the vendor.

Prototype configuration:

```text
configure
set service print-server image localhost/vyarm-print:live-e-20261004
set service print-server listen-address 192.168.178.173
set service print-server allow-client 192.168.178.84/32
set service print-server usb-port 4-1.2
commit
```

CUPS web UI: `https://192.168.178.173:631`, user `printadmin`. The random test
password is in `/config/profile-e/admin-password`, readable only by root.
The certificate is locally generated. Printer/driver/paper/queue administration
is performed through CUPS, not duplicated in VyOS CLI.

Alternative USB forwarding (remove the CUPS USB grant first):

```text
configure
delete service print-server usb-port
commit
set service usb-server allow-client 192.168.178.84/32
set service usb-server allow-usb-id 1343:0005
commit
```

A shared explicit device assignment is rejected at commit. No device is exported
unless its ID is listed; the prototype ID allowlist applies to all devices with
that VID/PID. It is not yet a per-serial-number allowlist. Before forwarding a
printer, pause its CUPS queue to prevent new jobs waiting on an unavailable USB
backend. Automated queue coordination is still required.

Both services default to inactive until configured. The prototype's dedicated
nftables input tables restrict TCP 631/7575 to configured IPv4 client networks;
they do not override existing VyOS deny rules. Native firewall integration,
IPv6, dynamic VPN addressing and firewall reload reconciliation are still to be
implemented. Tailscale/WireGuard access has not been tested in this live run.

## Storage and lifecycle

CUPS configuration, job spool and logs live below `/config/profile-e`. A service
restart recreates the container and retains its queues. Maximum request size is
100 MiB, max queued jobs 100; this is not an aggregate disk quota. Successful job
files are not retained. VH config and any optional license stay outside the
receiver container. Changing/restarting a receiver must not restart VH.

The live installer adds temporary templates plus the matching VyOS XML
reference; it backs up that reference under `/config/profile-e`. Release builds
must instead compile proper native XML definitions. The prototype uses volatile
systemd units and is intentionally not saved into config.boot yet. Do not
reboot expecting these experimental services to be persistent.

## Remaining integration work

- Add independent E build/runtime installation, common E/G component resolution,
  image manifests and all-board build checks, including E52C A-C+E.
- Generate native XML/operational commands, transaction-safe reconciliation,
  update/remove/rollback handling and installation/migration tests.
- Stable serial/port ownership, reconnect handling for passed USB device nodes,
  CUPS queue pause/resume, aggregate storage limit and log rotation.
- Preserve only explicitly selected device access; verify container isolation.
- Exercise VPN access, other boards, Windows-client behavior, gamepad controls,
  and printing through VH separately from USB enumeration.

Sources: [CUPS](https://openprinting.github.io/cups/),
[VirtualHere server](https://www.virtualhere.com/usb_server_software),
[server settings](https://www.virtualhere.com/configuration_faq),
[client service limitation](https://www.virtualhere.com/client_service).
