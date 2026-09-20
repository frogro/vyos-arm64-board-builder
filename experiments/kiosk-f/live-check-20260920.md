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
