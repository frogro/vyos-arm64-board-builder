# Non-disruptive live checks, 2026-09-20 around 12:20 CEST

ROCK 192.168.178.173, container kiosk-test. No service restart or configuration
change performed during these checks.

- Container service active since 11:34:39; Result=success, NRestarts=0.
- Display status HDMI-1, rotation 90, logical 1080x1920; physical touchscreen
  mapped at /dev/input/event4. This is runtime status, not a new visual touch test.
- /config/kiosk-test/state mounted at /state; browser directory and Sunshine
  pairing-state file present. This does not establish image-update survival.
- Sunshine administration published exclusively on 127.0.0.1:47990. Connection
  from ThinkPad to ROCK LAN address port 47990 refused.
- Unauthenticated HTTPS GET requests on loopback to /, /api/config, /api/apps
  and /api/clients/list each returned HTTP 401. No credentials or state contents
  were read. curl used -k to test authorization independently of certificate trust.
- Presented certificate subject and issuer both CN=Sunshine Gamestream Host;
  validity 2026-09-19 through 2046-09-14. Client trust has not been established;
  these checks do not resolve the browser certificate warning.
- Sunshine configuration has lan_encryption_mode=2, wan_encryption_mode=2,
  upnp=disabled and stream_audio=disabled. No new streaming session or encrypted
  traffic verification was performed.
- Journal still contains Chromium DBus/UPower/GCM warnings and Xorg references
  to unexposed input nodes. Do not grant broad device access merely to hide them.
- Separate failure: modem-connect-recover.service timed out after 120 seconds
  following FM350 USB re-enumeration, ending 11:49:32 without a working data
  path. Cause and current modem connectivity need a separate investigation;
  network settings were left untouched.

Pending: built CLI package validation and interactive help/completion tests,
USB hotplug with user hardware, second connected display, image-update/rollback
test, and final certificate/access setup. Current working kiosk remains intact.

## Sunshine CLI source/companion build follow-up

Commit 98dd656 implements the separate Sunshine supervisor, native persistent
remote access/input/audio policy and operational status/pair/revoke/credential
recovery commands. 34 experiment tests passed, including actual subprocess
supervision with a dummy Sunshine and an independent desktop process. Native
VyOS config and op-mode schema/template generation passed. No claim of a new
live CLI deployment or hardware audio/stream test.

Built `localhost/vyarm-kiosk:sunshine-cli-98dd656` on ROCK without activating it:
image ID `15360200c7ca616c21b51eba17fbe4cc1e8053d810db4c6b164f0f3b78b6d6eb`.
An isolated unprivileged instance with no network, no host state mounts and all
capabilities dropped successfully imported the helper and compared the actual
Sunshine --creds output against the reset helper's reverse-byte uppercase SHA256
format using disposable test-only credentials. No real credentials were read,
printed or changed.

Docker package snapshot prepared under tmp/kiosk-sunshine-build-20260920,
version suffix `+kiosk-sunshine.f303bf1f1928`, pinned upstream 27383e4f1 and same
KVM/Tailscale recipe as installed. Initial Docker startup is awaiting the local
Ubuntu pkexec authentication dialog; no package success is implied by this note.
Kernel service vyos-f-test-kernel continues compiling. A 10-minute thread
heartbeat monitors both builds and reports actionable changes/completion only.
Monitor deliberately off and modem deliberately disconnected per user; neither
is a test failure or permission to change modem/network settings.

## Sunshine CLI live rollout, 18:07 CEST

Installed verified vyos-1x package +kiosk-sunshine.f303bf1f1928 on ROCK.
Postinst identical to previous package; dpkg --audit empty. Backup under
/config/kiosk-test/backups/sunshine-cli-20260920 includes prior package
+kiosk.72cc8e8c3d84, config.boot, session helper, Sunshine state and container
inspection, plus manual rollback notes (directory root-only).

Native interactive completion verified: show kiosk sunshine offers kiosk-test;
its commands clients/pending/status have help; remote audio offers enabled and
disabled with explanation distinguishing stream audio from local HDMI audio.

Companion migration commit failed validation because configured device input2
(/dev/input/by-id/usb-ILITEK_ILITEK-TP_V06.00.00.00-event-if00) is absent. No
container restart occurred. Candidate discarded; bind-mounted session helper
restored byte-for-byte from backup. Saved config.boot unchanged (cmp).
Current container remains localhost/vyarm-kiosk:cli-test. Asked user to reconnect
USB touchscreen before retrying. No device/network/modem/firewall edits made.
Sunshine runtime policy, access/input/audio changes and pairing API live tests
remain pending; package installation and completion are not runtime acceptance.

## Sunshine CLI runtime test, 18:13–18:15 CEST

Touchscreen reconnected as event4/event5; native migration commit succeeded after
restoring new session helper and selecting sunshine-cli-98dd656. User confirmed
local touch works again after container restart. Runtime display HDMI-1/90,
1080x1920; physical touch event4 enabled with matching rotation matrix.

Native show kiosk sunshine kiosk-test status works. Tested remote access disabled
(commit): running false; enabled (commit): running true. Tested input view-only
and audio enabled together: Sunshine config keyboard/mouse/native_pen_touch=false,
stream_audio=enabled. Restored control/audio disabled via native commit/save.
Throughout remote-only commits container StartedAt stayed 18:12:57.173924765 CEST,
Xorg host PID 734074 and Chromium host PID 734228 unchanged. No desktop restart.
Unauthenticated local HTTPS administration returns 401 after re-enable. Full
sunshine_state.json compares equal to backup without exposing its contents; all
non-CLI-owned Sunshine config lines preserved.

Limitations: no real audio source/playback test, no new pairing/revoke/password
reset (existing credentials and clients preserved), no fresh Moonlight input
test in view-only mode, no image-update test. H264 rkmpp capability found.
Status note 'Creating = selected' is too strong: startup probes also log Creating
for failing NVENC/VAAPI attempts. Correct wording before next package build;
these logs alone do not prove an active stream encoder.

USB reconnect did not restore old container touch until recreation; generic
hotplug/reconciliation remains an open issue rather than being declared solved.

## USB touch reconnect recovery

Reproduced disconnect/reconnect with identical event4/event5 numbers. Xorg still
listed the old touch registration; manual xinput disable/enable of the physical
touch device restored input, confirmed by user, without restarting desktop.
The read-only udev database exposes updated DEVPATH and USEC_INITIALIZED even
when container Xorg does not process host hotplug removal/addition.

Display watcher now compares generation and stable USB identity for already
exposed touch devices. Reopens same-device reconnect and reapplies rotation.
Missing devices skipped during enumeration; no fixed vendor/model IDs. Different
identity refused, intentionally disabled inputs not enabled, failed enable retried.
Nine display tests pass (including reconnect between polls, disconnect, identity
change, disabled device and failed enable retry).

Live companion image touch-reconnect-20260920, ID
177f8d154126092e5ae3bf3ae81f4d2d546406edfd24cc4566b3ecdcef45a21f,
contains changed display helper; host bind helper updated too, previous helper
backed up in sunshine-cli-20260920. Native image commit succeeded, portrait and
event4 reported. Post-start Xorg PID 758991, Chromium PID 759079. Awaiting user
unplug/replug test. This is limited recovery for existing node numbers; changed
event numbers/new devices still require host/container device reconciliation.
