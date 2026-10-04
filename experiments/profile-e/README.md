# Profile E: print server — live prototype

E is reserved for independent CUPS printing and optional USB forwarding on all
supported boards, including E52C. The previously proposed remote-maintenance
profile moves to **H**. E does not require D/F/G. G may select the same shared
VirtualHere component; there must only be one server and one `service usb-server`
configuration, even with E+G.

Profile E is selected with `PRINT_SERVER_E=yes` or the `print_server_e` workflow
input. The builder stages a checksummed offline CUPS/Gutenprint image in the SD
image and update ISO, imports it before VyOS configuration loading, and compiles
its native CLI with the selected upstream VyOS package. Defaults remain off.
The first integrated build and reboot/update qualification are pending; existing
published images do not gain E retroactively. No proprietary VirtualHere binary
is distributed in images.

## Architecture and current live CLI

CUPS/Gutenprint run in a Podman container; VirtualHere runs as a separate native
service. The generic official ARM64 VirtualHere build was downloaded directly
for the test (4.8.8, SHA256
`09deced5586ed37b8b3db7a6187d84029f65d487c3c2b24a949b993b3d582077`).
The Linux console client runs as a normal application, not as a licensed client
daemon. Only one USB device is shared. Proprietary software distribution remains
to be settled before including it in public images; prefer explicit on-demand
installation from the vendor. The checksum-pinned installer is now
`cli/install-virtualhere.py`; it writes the validated executable and provenance
to `/config/profile-e/virtualhere-bin`. A changed vendor binary fails validation
and does not replace an existing installation. It never enables the service.

Configuration for a newly built E image (`auto` uses its bundled runtime):

```text
configure
set service print-server image auto
set service print-server listen-address 192.168.178.173
set service print-server allow-client 192.168.178.84/32
set service print-server usb-port 4-1.2
commit
```

CUPS web UI: `https://192.168.178.173:631`, default user/password `vyos` / `vyos`. Change it with
`request print-server password` (operational mode, hidden interactive input).
The password is stored in `/config/profile-e/admin-password`, readable only by
root, and existing passwords are never replaced by the first-start default.
This changes only CUPS, not the VyOS login. Configuration must be copied during
ISO updates to retain this state. Password changes restart the print service;
wait until current printing is complete.
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

An overlapping explicit device assignment is rejected at commit. No device is exported
unless its ID is listed; the prototype ID allowlist applies to all devices with
that VID/PID. It is not yet a per-serial-number allowlist. CUPS owns job scheduling: new queues default to `retry-job`, so jobs remain
queued while the selected USB device is unavailable and can resume when it is
available. Existing queues retain their chosen policy; change it in the CUPS
web UI or with `lpadmin -p QUEUE -o printer-error-policy=retry-job` inside the
container. Do not switch USB ownership during an active physical print; a retry
cannot guarantee that a partly printed job will not be printed twice. Switching
USB ownership is explicit; there is no second custom job scheduler.

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

`cli/prepare-source.py` now stages native XML definitions and owners for the
upstream build: E provides print-server plus shared usb-server, G alone provides
only usb-server, and E+G adds it once. These definitions passed the upstream
RelaxNG schema and command-template generator. Release workflow selection now invokes this source preparation; the complete
ARM64 package and image build still need to pass.

The developer-only live installer adds temporary templates plus the matching VyOS XML
reference; it backs up that reference under `/config/profile-e`. Release builds
must instead compile proper native XML definitions. The live prototype configuration is not saved into config.boot yet. For the
integrated image, the native owner recreates runtime units at boot from saved
VyOS configuration. Printer state, password, USB bindings and user-installed VH
remain under `/config/profile-e`. Use `save` after a successful commit. A reboot
and ISO update test is still required before claiming update qualification.

## Remaining integration work

- Qualify the integrated E build/runtime and common E/G component on the ROCK,
  including full package generation, image manifests and ISO update. E is allowed
  independently on E52C and Pi; hardware tests for those boards remain open.
- Generate native XML/operational commands, transaction-safe reconciliation,
  update/remove/rollback handling and installation/migration tests.
- Qualify return-to-CUPS job resumption and complete aggregate storage limits.
  CUPS rotates its logs at 1 MiB; this is not an aggregate spool quota.
  CUPS now supervises the selected physical ports and recreates device grants
  after disappearance/reappearance. A changed VID/PID or available USB serial
  is rejected. The RX1 exposes no standard USB serial descriptor; it is matched
  by physical port and VID/PID. Physical replug and reboot remain separate tests.
- Preserve only explicitly selected device access; verify container isolation.
- Exercise VPN access, other boards, Windows-client behavior, gamepad controls,
  and printing through VH separately from USB enumeration.

Sources: [CUPS](https://openprinting.github.io/cups/),
[VirtualHere server](https://www.virtualhere.com/usb_server_software),
[server settings](https://www.virtualhere.com/configuration_faq),
[client service limitation](https://www.virtualhere.com/client_service).

## VirtualHere installation

On E or G images, run `request usb-server install` explicitly. This downloads
only the reviewed vendor ARM64 binary; a changed upstream download is rejected
until its version/checksum is reviewed. It leaves the server disabled. Enable
`service usb-server` only after setting allowed clients and device IDs. The
free-server restrictions still apply. E+G provides the same command and service
once. `service usb-server disable` stops it without deleting state or a license.

Profile H remains reserved for the previously discussed remote-maintenance
profile; it is not implemented or silently enabled by selecting E.
