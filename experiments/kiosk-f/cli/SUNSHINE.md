# Sunshine CLI experiment (profile F only)

Source implementation; not yet installed or accepted on the live kiosk.
The native kiosk URL/output/rotation package passed the earlier live test.
This extension requires BOTH the new vyos-1x package AND the companion image.
It does not add H.265, RGA, PulseAudio or a local HDMI audio configuration.

## Persistent settings

```
configure
set container name kiosk-test kiosk remote access enabled
set container name kiosk-test kiosk remote input control
set container name kiosk-test kiosk remote audio disabled
commit
save
```

Use your actual container name. Values complete with Tab and have value help.
Defaults are access disabled, view-only, audio disabled. Local touch remains
independent. Audio enabled requests Sunshine stream audio; actual sound still
requires a functional audio source/session in the container. No capability probe
is presented as a successful sound test.

The native container owner generates an atomic read-only policy bind at
/run/vyos-kiosk/NAME -> /run/vyos-kiosk-policy. Only changes to the remote node
skip a container restart, and only when the running container already has that
exact read-only bind. First deployment/image changes use the normal lifecycle.
The supervisor stops/restarts Sunshine for policy changes without restarting
Chromium, Xorg or the local touchscreen watcher. Existing streams are ended.
The supervisor fails closed on a missing/invalid policy and requires initialized
Web credentials before starting Sunshine. A newly deployed image with no remote
node therefore has remote access disabled, not implicitly granted.

## Operations (native administrator permissions)

```
show kiosk sunshine kiosk-test status
show kiosk sunshine kiosk-test clients
show kiosk sunshine kiosk-test pending
request kiosk sunshine kiosk-test pair
request kiosk sunshine kiosk-test revoke
request kiosk sunshine kiosk-test reset-credentials
```

Status is local and needs no Web password. Other API operations prompt for the
existing Sunshine Web username/password; pair also prompts for the pending ID,
name and PIN, and revoke for the UUID. Revoke ends current Sunshine sessions as
well as removing the selected pairing. Credential recovery prompts for a new
username/password, does not require the forgotten password, and preserves other
state fields and pairing certificates. It interrupts streams but not Chromium.
No passwords/PINs enter CLI arguments, saved VyOS config or helper logs. There is
no new sudo role or remote management listener. The control socket is mode 0600,
owned by the existing kiosk account, reached via native administrative Podman.

The pinned Sunshine revision is 63d35f702ee9e362e43263742981836ec0710384.
Its PIN API requires a 32-character pairing ID. Requests use loopback HTTPS with
an exact certificate pin from persistent state, no redirects and bounded reads.
Credentials are salted SHA256 with Sunshine's reverse-byte uppercase hex format;
reset happens while Sunshine is stopped, atomically, preserving the rest of the
JSON state. Paths outside /state/sunshine are refused for credentials/certificates.

## Ownership and compatibility

CLI owns access plus stream_audio, keyboard, mouse, native_pen_touch, controller,
lan_encryption_mode, wan_encryption_mode and upnp. Encryption is required (2) on
LAN/WAN, UPnP and gamepads stay off. Keyboard/mouse/pen/touch follow input mode.
The supervisor reconciles these keys when the Web GUI changes them; configure
them in VyOS, not in both places. Other lines/settings (encoder, capture,
audio_sink, ports, certificate paths etc.) are preserved. A one-time original
config backup is retained. Changes to unmanaged keys still use Web Save/Apply.
No firewall, port publication, binding or routing settings are created/changed.
Existing SSH-tunnel/local-only Web publication remains required; container NAT
means Web origin scope and host loopback publication must not be conflated.
Disabling access stops Sunshine including its Web UI; CLI recovery still works.

The image label io.vyarm.kiosk.sunshine-policy=1 is checked before accepting a
remote node. The companion image must contain the matching session supervisor.
Lab bind mounts overriding /usr/local/bin/kiosk-session.py must be updated to the
same version or removed as part of image migration; an old supervisor ignores the
policy. Do not claim a working deployment from a label alone.

## Rollout and rollback

Before live deployment back up config.boot, the installed package, current image
ID, helper bind sources and /state/sunshine. Explicitly migrate current access,
input and audio choices; do not overwrite an existing install with fresh defaults.
Use normal commit/save with the matching image and supervisor; then verify
status, Web login, pair/revoke, view-only, audio on/off, untouched browser PID,
config persistence and restart. Those live/API/hardware tests remain pending.

Before package downgrade remove the remote node and restore the prior image and
session supervisor. Preserve or explicitly restore desired audio/input/encryption
values from backup; the old supervisor does not apply the new policy. Before
downgrading past the earlier kiosk package, additionally convert kiosk values to
legacy environment nodes as documented in README.md. Image update/reboot and
actual downgrade have not been established by source tests or a package build.
