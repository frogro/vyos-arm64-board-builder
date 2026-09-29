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

See profiles/b-hardware/kernel-patches/orangepi5-plus/README.md, patch 0005.
No live kernel replacement was performed. Firmware device-link warnings are
not hidden by this patch and remain separately observable.

## Locale helper

Explicit bash invocation previously produced no valid configuration session;
the same minimal session check succeeded under vbash. The helper now selects
vbash and vyattacfg, verifies its session directory, does not swallow compare
errors, and saves to /config/config.boot explicitly. Live invocation through
bash successfully persisted the user's DNS, timezone and NTP selections;
Chrony synchronized to the selected source. Firstboot contract tests pass.
