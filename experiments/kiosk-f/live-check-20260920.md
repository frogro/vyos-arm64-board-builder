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
