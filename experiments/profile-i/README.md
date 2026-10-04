# Profile I: media administration

I adds pinned Anthias media administration and a local browser player. Selecting
`SIGNAGE_I=yes` / `signage_i: true` automatically selects F, but not C, D, E or G.
The current main board selection permits ROCK 5B and Orange Pi 5 Plus; the
expanded board branch supplies its own Pi 5 support policy.

## Runtime and configuration

The image carries offline ARM64 application and Redis images. The import service
checks archive and image identities before native VyOS configuration is loaded.
Installation alone starts neither the management server nor a kiosk.

Configure an F Wayland kiosk named `signage-i` with the usual board display,
input, audio and persistent browser-state grants, then set (omit the network
deletion if no container network is assigned):

```text
configure
delete container name signage-i network
set container name signage-i allow-host-networks
set container name signage-i kiosk url 'http://127.0.0.1:8089/player'
set container name signage-i kiosk display-backend wayland
set service signage kiosk signage-i
set service signage allow-client '192.168.178.0/24'
commit
save
```

`allow-client` can also be a routed VPN IPv4 network. Router firewall rules still
apply. Management uses TCP 8088; the player, Redis and browser debugging listener
are loopback-only. The initial management login is `vyos` / `vyos`; change it in
Settings. Existing users/passwords are preserved, not reset by container startup.
DNS and synchronized system time must be configured for external HTTPS content.

Settings contains display selection, rotation, mute and playback hours directly.
Changes use a validated host request followed by the normal VyOS commit/save
path. F owns `kiosk audio-muted` and `kiosk display-schedule start/stop/days/timezone`.
The latter blanks the browser and stops playback outside the selected hours;
it does not switch physical monitor power via CEC. Older F images without the
matching capability label are rejected for these options.

## Data and update boundaries

Program files reside in `/usr/share/vyos-arm64-board-builder/signage-runtime`.
Media, Anthias database/settings and last valid playlist reside in
`/config/profile-i`. The offline Podman images use the common persistent store.
ISO updates must copy the configuration directory; declining this deliberately
starts a separate configuration. An actual I ISO-update/reboot test is still
required before claiming verified update persistence.

Web Backup & Restore includes Anthias settings, users, database and media. It
is not a backup of the whole router or of the F CLI configuration. Save that
configuration using native VyOS facilities. Restore preflights expanded size.

HTTP uploads are limited to 2 GiB per file, with an 8 GiB data budget and a
1 GiB free-space reserve; temporary processing space is also considered. These
are application admission checks, not a filesystem quota. Background remote
media downloads and processing output need additional resource accounting before
this can be advertised as a hard media-storage cap. A backup larger than the
HTTP upload limit currently needs a different restore path; do not promise
unrestricted web restore. Deleting the UI's Import content section does not
remove the normal Add Asset upload facility.

The pinned upload policy currently admits video through 1920×1080. Container
format and codec must be supported by Chromium; no automatic transcoding is
provided. Browser decode policy remains F's responsibility.

## Recovery

The independent loopback player keeps the last valid playlist and its local
media available while management is unavailable. Expired schedules are respected;
no eligible content produces a fallback message. Direct web navigation returns via
an external controller without changing decoder configuration. Offline third-party
webpages are not cached. Periodic status reads fixed container files using the
verified PID instead of spawning `podman exec` processes.

## Source pins and licensing

Anthias application source: Screenly/Anthias
`f5baca27f40ed604824767c3ea15632c96e95fd5` (v2026.9.0).
ARM64 manifests are fixed in `container/Containerfile` and `build-runtime.sh`.
The adapter uses that version's playlist and upload-policy internals; upgrading
the pin requires contract and live playback tests. No automatic Anthias updater
is exposed. Anthias-derived templates retain their GPLv2 license; see
`ANTHIAS-LICENSE`. The vendored websocket-client includes its upstream license.

## Validation so far

- Local ROCK backup: 16 media files byte-identical after isolated restore;
  SQLite integrity and restored settings/user records verified.
- Oversized HTTP request rejected before body; normal photo upload/create/delete.
- Fresh container creates login; changed password survives container restart.
- Recreated application/Redis/worker stack serves management and independent
  player with copied live data; clean stop removes all three containers.
- Outside playback hours, the browser debugging listener is closed; the
  navigation controller cannot override the blank page. Continuous playback restored.
- Native CLI source generation checked against pinned upstream, including I+F
  and cumulative C/D/E/F/G/I selection.
- Remaining: image build, full boot and ISO-update validation, storage accounting
  above, and a longer unattended playback run.
