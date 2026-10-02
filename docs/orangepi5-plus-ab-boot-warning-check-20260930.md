# Orange Pi A/B boot-warning investigation, 2026-09-30

Live image: 999.202609281945-op5-ab-f3e3ed0, Linux 6.18.50-vyos.

## Early hostname resolution

Native /usr/libexec/vyos/init/vyos-router sets the saved hostname early for
FRR (T5239). Journal monotonic timestamps show hostname set at 36.893 s,
sudo invoking system_host-name.py warning at 42.600 s, and vyos-hostsd
writing /etc/hosts at 42.870 s. This precedes the common AP setup helper.
The existing timezone/hostname try-restart correction for rsyslog remains.

Enable the already installed libnss_myhostname provider after files and before
DNS in nsswitch.conf. The finalizer checks that the provider exists and refuses
unfamiliar hosts action clauses rather than silently changing their semantics.
This applies to common finalization for SD/eMMC and update-ISO root filesystems.

Live test in an isolated UTS namespace, without changing the actual hostname:
getent hosts vyos-early-hostname-check failed (exit 2) before the change; it
resolved afterwards and sudo -n true succeeded without a hostname warning.
Normal IPv4 self-resolution still returns 127.0.1.1, external DNS works,
rsyslog and chrony are active. Backup: /config/backups/nsswitch.pre-early-hostname.
Full reboot confirmation remains pending.

## Power domains

See profiles/base-hardware/kernel-patches/orangepi5-plus/README.md, patch 0005.
No live kernel replacement was performed. Firmware device-link warnings are
not hidden by this patch and remain separately observable.

## Locale helper

Explicit bash invocation previously produced no valid configuration session;
the same minimal session check succeeded under vbash. The helper now selects
vbash and vyattacfg, verifies its session directory, does not swallow compare
errors, and saves to /config/config.boot explicitly. Live invocation through
bash successfully persisted the user's DNS, timezone and NTP selections;
Chrony synchronized to the selected source. Firstboot contract tests pass.

## Live follow-up, 3 October 2026

Image 999.202610021837, Linux 6.18.54, exposed a third NSS writer:
`security_reset()` in `/usr/libexec/vyos/init/vyos-router` resets the hosts
policy before the saved configuration is loaded. Patching only the installed
NSS file and login template left this early window uncorrected. The common
patcher now validates and patches all three locations before writing any.

Live Orange Pi reboot d699a11a-afb6-423d-a2b6-8f3e943b287e passed without the
hostname warning after modifying this one hosts line. Backups are under
`/config/backups/hostname-live-20261003`. Native CLI, SSH, DHCP/default route,
DNS and services passed, with no failed units.

The inherited ttyAMA0 configuration was then replaced through native CLI by
`system console device ttyS2 speed 1500000`, without the `kernel` flag.
The DT selects serial2:1500000n8. Reboot
98c6efca-18e5-44c3-b6d8-36cd549d73cf confirmed agetty on ttyS2/1500000,
`console=tty0` retained, no ttyAMA0 or hostname warning, and healthy SSH,
networking and rsyslog. No physical UART client was attached; serial electrical
operation/login is not claimed as tested. Backups are under
`/config/backups/console-live-20261003`.

ROCK 5B's Linux 6.18.54 `rk3588-rock-5b-5bp-5t.dtsi` likewise selects
serial2:1500000n8. EDK2 ROCK/Orange Pi builds now correct factory defaults and
raw factory config to this UART login while retaining HDMI kernel output.
The existing E52C native-extlinux kernel console and Pi paths are unchanged.
Imported customer configurations are not rewritten during ISO updates.
The helper was tested using the live VyOS ConfigTree library for idempotence,
HDMI preservation, preservation of unrelated settings and the existing
extlinux kernel-console behavior.

Persistence shutdown remains unchanged, per `kvm-shutdown-storage.md`.
The observed Chrony/VyOS/FRR shutdown ordering cycle also remains unchanged:
vyos-router.service, the FRR override and Chrony override template match
upstream vyos-1x commit 5c515753e byte for byte. This is separate from the NSS
and factory-console fixes; no claim of a warning-free entire journal is made.
