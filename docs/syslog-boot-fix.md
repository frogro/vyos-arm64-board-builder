# Syslog startup ordering (19 September 2026)

Observed on ROCK 5B image 999.202609161112: system_timezone.py restarts
rsyslog at uptime 36.7 seconds, before system_syslog.py creates
/run/rsyslog/rsyslog.conf at 42.3 seconds. The premature start fails;
native syslog application subsequently succeeds.

The checksum-verified 999.202609191517 ROCK network/tailscale/kvm ISO still
contains the unconditional restart. The common rootfs finalizer now patches
that command to try-restart. Running rsyslog still reloads the timezone;
initial startup remains owned by the native syslog configuration. No new
configuration node or service is introduced. Unknown upstream code fails
patching for review; applying the same patch twice is safe.

Live installation: original file saved at
/config/system_timezone.py.before-syslog-fix. rsyslog restarted successfully
and a test message reached /var/log/messages. No failed units remained.
A reboot test of the corrected boot ordering remains outstanding.
Installing the already-built 1517 image will not carry this patch; it needs
reapplication for testing or a subsequent build containing this change.

Separate observation: at the NTP time step, timer-driven logrotate and
rsyslog size-triggered logrotate overlapped. The latter exited with lock
failure code 3 while the former completed. Rotation settings are unchanged;
this startup patch does not claim to fix that separate race.
