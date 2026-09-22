# Kiosk live-test CLI

Current summary: portrait and local touch passed container restart and full
router reboot; see the final result below. Earlier dated sections retain the
investigation history and are not the current state. No image-update test or
dedicated `service kiosk` schema has been completed.

The next CLI prototype now extends the existing container owner with
`container name NAME kiosk` rather than introducing a separate service owner.
See [cli/README.md](cli/README.md) for source-generation tests and migration.
It is NOT installed live yet; the working commands below remain applicable.

Experimental branch only. The tested control surface uses the existing native
VyOS `container` configuration. `service kiosk` is still a design, not an
installed command. This avoids replacing CLI caches or changing permissions.
The example container is named `kiosk-test`; use your actual container name.

## URL and orientation

```
configure
set container name kiosk-test environment KIOSK_URL value 'https://example.org/'
set container name kiosk-test environment KIOSK_OUTPUT value 'auto'
set container name kiosk-test environment KIOSK_ROTATION value '90'
commit
save
exit
```

Rotation 0 = normal, 90 = left/counterclockwise, 180 = inverted, 270 = right.
`auto` selects the connected primary output, or the sole connected output.
With multiple connected outputs and no primary, select an output explicitly.
The existing physical mode and refresh rate are retained; logical browser
width/height are swapped by Xorg for 90/270 degrees. No Moonlight client settings
are modified. Stream aspect ratio/letterboxing and remote absolute input need
separate portrait-session testing.

Accepted URL schemes are http, https and local absolute file URLs. URL values
are passed as an argument, never evaluated by a shell. Container environment
values are free-form in upstream VyOS: kiosk validation happens on startup,
NOT during `commit`. An invalid value can therefore stop the kiosk; correct it
and commit again. Production `service kiosk` must validate before commit/apply.

## Stop and disable automatic start

```
configure
set container name kiosk-test disable
commit
save
exit
```

## Start and enable automatic start

```
configure
delete container name kiosk-test disable
commit
save
exit
```

This is native persistent enable/disable, not a separate transient pause.
The container's restart policy for crashes is separate from boot activation.

## Status and restart

```
show container
show container log kiosk-test
restart container kiosk-test
```

Administrative diagnostic command for display selection and touch mapping:

```
sudo podman exec kiosk-test cat /run/kiosk/display.json
```

Only already-exposed physical devices marked `ID_INPUT_TOUCHSCREEN=1` by udev
receive a rotation/output transformation. No USB vendor/product allowlist is
used. Relative mice and Sunshine's virtual input are not deliberately remapped.
The monitor re-enumerates every two seconds. It does not add host devices to the
container: native device mappings and hotplug permissions are a separate concern.
Existing libinput calibration is retained. Actual touchscreen/remote-input
correctness after rotation still needs hardware/user validation.

## Build and rollback

Build `container/Containerfile.cli` with `container/` as context on the ROCK,
as image `localhost/vyarm-kiosk:cli-test`. It extends the validated local
`localhost/vyarm-kiosk:mpp-test` image with xinput and the two Python helpers.
This is a local prototype, not a portable registry image. The lab still mounts
`start-kiosk` and `kiosk-session` from `/config/kiosk-test/build/`; deploy the
matching scripts when selecting the new image.

Backups: `/config/kiosk-test/start-kiosk.before-cli`,
`/config/kiosk-test/kiosk-session.before-cli`, and
`/config/kiosk-test/config.boot.before-cli`. To roll back, restore only those
two scripts, select `localhost/vyarm-kiosk:mpp-test` via native configuration,
and remove the two new environment variables. Restore the prior URL if changed.
Do not overwrite the whole router configuration from an old backup.
Pairing state and browser profile remain in the existing persistent state volume.
No extra host privilege or network listener is introduced.

## Live results (2026-09-20)

- Four local tests passed: configuration rejection, literal URL handling,
  output/geometry selection, and touch transformation math.
- Native `commit` selected `localhost/vyarm-kiosk:cli-test` successfully.
- Rotation 90 produced 1080x1920; returning to 0 restored 1920x1080.
- Chromium's process arguments contain the configured local test URL.
- `restart container kiosk-test` succeeded after fixing PID 1 signal forwarding.
  Journal: stop 02:39:15, deactivated successfully 02:39:18 CEST. The prior
  starter required SIGKILL after ten seconds and exited 137.
- Sunshine again detected h264_rkmpp after restart. A new paired client session
  after these changes has not yet been checked by the user.
- Touch mapping inventory is empty: rotated physical touch and remote absolute
  input are NOT yet validated. Existing Xorg warnings about inaccessible event4
  remain; no broad input-device access was granted to hide them.
- Final state is enabled, rotation 0, output auto, original local test URL,
  committed and saved. No router reboot was performed; persistence across a
  full reboot remains a separate test.

## Client tuning and latency observations

User accepted Moonlight H.264, 1080p/60 with forced hardware decoding, VSync off,
and 8 Mbit/s as "almost perfect" on 2026-09-20. This is a client preference,
not an image default or a universal recommended bitrate. Resolution and frame
rate were retained. User observes slight initial mouse-motion delay compared
with direct local input; its cause is not established.

Sunshine stream_audio is disabled. A roughly 19-second wlan0 capture recorded
2934 outgoing video packets and zero outgoing packets on the audio port. Video
payload averaged 1.741 Mbit/s in that sample; packet-group gaps had median
16.67 ms, 95th percentile 38.31 ms, maximum 47.77 ms. These are packet timings,
not measured frame rate or end-to-end mouse latency. No payload was retained.
Fifteen ICMP probes averaged 1.168 ms with zero loss; this short sample does not
establish absence of video packet loss. Intel video-engine counters increased
while Moonlight was running, confirming active hardware decoding. Sunshine has
an attached SysV shared-memory segment, consistent with its X11 SHM capture.
ThinkPad WLAN power saving was on; no privileged local change was made.

## Boot readiness correction

The first full reboot exposed a DHCP ordering failure: the container attempted
its explicit host-address port binds at boot +47 s, before DHCP supplied that
address at +49 s. Native restart=no left it failed, and the boot configuration
activation omitted the failed container section. The container section was
restored in isolation from the pre-change backup, with current kiosk settings.
Never save an incomplete active configuration following a failed boot/commit;
`exit` in the vbash configuration environment is not a reliable substitute for
terminating a shell script. Save only inside a successful-commit branch.

The lab now uses native `restart on-failure`, plus a **prototype systemd drop-in**
for this container only. `systemd/wait-container-addresses.py` reads explicit bind
addresses from the generated Quadlet and waits up to 60 monotonic seconds for
those addresses to exist. Wildcard listeners do not require a wait. It neither
changes interface addresses nor broadens port exposure. Retry delay is five
seconds, without a start-rate cutoff. Manual service stop remains respected.

Live installation: `/usr/local/libexec/vyos-kiosk-wait-addresses` and
`/etc/systemd/system/vyos-container-kiosk-test.service.d/kiosk-retry.conf`.
The drop-in is intentionally separate from the generated native unit; it is
NOT an upstream VyOS CLI feature. Its files must be packaged/recreated by the
future profile for image updates; this live installation alone is not update-safe.
The sample drop-in names kiosk-test; production generation must use the selected
container name. A changed DHCP lease address still requires correcting the
explicit published-address configuration; waiting cannot resolve a stale address.

The second reboot passed: native configuration retained the kiosk, the container
started at boot +49 s, and display state was 1920x1080/rotation 0. No failed
systemd units were reported; Sunshine detected h264_rkmpp. On this particular
boot the bind address was already present at the pre-start check. A separate
live test in an isolated network namespace withheld the address for two seconds:
the helper waited and returned after 2.02 seconds once it was added. The real
router interfaces were not modified. Six local unit tests passed.
Tailscale and KVM video services were also active after reboot; KVM had been
stopped manually during earlier performance isolation, so future comparisons
must account for this restored background workload. User confirmation of the
new Moonlight session and physical inputs remains outstanding.

## User acceptance and remaining shutdown defects

User confirmed the post-reboot session is usable and running very well at
8 Mbit/s. The previous-boot shutdown journal nevertheless shows two unresolved
kiosk-path defects at monotonic +530 s: Xorg caught signal 11 during teardown,
and Podman/netavark cleanup exited 125 because aardvark-dns attempted to create
a transient systemd scope after shutdown.target was already queued. systemd
therefore marked vyos-container-kiosk-test.service failed. These are distinct
from the later /run/live/persistence busy unmount. A successful normal restart
is not proof of a clean full-system shutdown. Current boot has no failed units.

Prioritize child-process/Xorg shutdown ordering and container-network DNS teardown
before calling this final. Do not suppress exit codes or remove networking/DNS
without checking the configured customer-URL requirements. Then package the live
helpers/drop-in for updates and add the planned native service schema/validation.
Rotated touch/remote-input verification and RGA/H.265 remain separate work items.

## Mobile touch monitor test (2026-09-20, in progress)

User confirmed landscape local touch is correct and very smooth. Generic USB
class discovery with --include-touch found the new touchscreen and pointer
interface; native device mappings were refreshed from that inventory. This is
still a snapshot, not automatic host hotplug reconciliation.

The first portrait startup produced a black screen reported by the user despite
Xrandr reporting a connected rotated output. Returning to landscape restored the
picture. A subsequent direct live Xrandr rotation remained visible, but touch was
wrong because the watcher still used the configured landscape rotation. The
watcher now reads the actual output rotation and includes it in its change
signature (including 0/180 and 90/270 changes with unchanged dimensions).
Seven local tests pass. A live 90-degree test reports 1080x1920 and the expected
touch matrix. User confirmed portrait touch works perfectly. A timed systemd job
returns the display to landscape. Saved configuration remains rotation 0.
The updated display helper is exposed via a native read-only display-helper
volume from /config/kiosk-test/build/kiosk-display.py.

The shutdown prototype now directly supervises the session bus and desktop
children as the unprivileged kiosk user (setpriv replaces the runuser wrapper).
It is exposed via a native read-only session-supervisor volume. Live restart
logs confirm children cleanup finishes before Xorg stops, but Xorg STILL reports
SIGSEGV at teardown; this is not a completed fix. no-name-server is saved for
the dedicated network and generated Quadlet has DisableDNS=true, but the existing
Podman network still has dns_enabled=true. Network recreation and full shutdown
validation remain pending. External name resolution currently works. Do not
claim the aardvark shutdown issue is fixed yet.

## Startup reset correction and repeat test

The portrait black screen was reproduced on direct container startup. Rotating
normal then left after Chromium was running restored the image. Xorg started
without -noreset, so short-lived readiness/setup clients could trigger automatic
server resets before persistent desktop clients connected. Xorg's own -help
confirms -noreset suppresses reset after the last client exits. The starter now
uses that option; normal SIGTERM shutdown remains enabled.

With -noreset, direct portrait startup and a subsequent native container restart
both returned a visible picture. User confirmed portrait and touch after the
repeat restart. Current state: saved rotation 90, 1080x1920, native service active,
Sunshine detects h264_rkmpp. The last non-debugger teardown logged desktop-child
cleanup, then "Server terminated successfully (0)" and service deactivation,
without the earlier SIGSEGV. Seven tests pass and shell syntax/diff checks pass.
This strongly implicates the startup reset sequence; it does not identify the
underlying Xorg memory fault. GDB changed reproduction (normal exit with and
without live rotation); no useful SIGSEGV backtrace was obtained. Temporary gdb
packages were confined to discarded live container layers, not the image.

Full router shutdown/reboot with this correction is still pending. The separate
stale Podman network/DNS cleanup issue described above remains unresolved.
Do not conflate successful container restart with full poweroff validation.

## Dedicated network recreation and persistence audit

Native `no-name-server` had generated DisableDNS=true but did not replace the
already-existing Podman network. Recreation used native commits: disable kiosk,
remove only the saved kiosk container and its network, then restore only those
81 commands from a current config backup. Merely detaching the network while
keeping even a disabled container is rejected by VyOS validation; that failed
candidate was discarded, not saved. Other router configuration was untouched.
The restored kiosk network now reports dns_enabled=false. The container inherits
host resolvers (in this lab 1.1.1.1 and 9.9.9.9), and external lookup succeeded.
This removes unnecessary internal container-name discovery for this single-app
network, not DNS functionality for customer websites.

Podman graph root is /usr/lib/live/mount/persistence/container/storage, so local
images use the native persistent store. Native saved container configuration
retains environment, volumes and devices. Browser and pairing state are bound
under /config/kiosk-test/state; live helper scripts are under /config as well.
This does NOT establish tested image-update compatibility: the address readiness
helper under /usr/local/libexec and its /etc/systemd drop-in are outside this
persistence scheme. Production profile F must package/recreate those components,
provide a reproducible versioned container image and test add-system-image plus
rollback with existing state. Device mapping still needs generic enumeration
reconciliation. Whole-router reboot validation is now in progress.

### Full reboot result

Completed full ROCK reboot on 2026-09-20. Boot ID changed from
3f96dd4f-6e57-4995-aa72-45d331cd9f7d to ac7699a9-fd43-484d-bfac-b5f640645526.
User confirmed portrait and touch after boot. Runtime reports 1080x1920/90,
network DNS plugin remains disabled, Sunshine detects h264_rkmpp, and systemd
reports zero failed units. Prior shutdown: desktop children stopped +1606.262,
Xorg terminated successfully (0) +1606.442, native container service deactivated
successfully +1607.121. No aardvark transient-scope/exit125 failure in this shutdown.
Remaining unrelated host shutdown messages include routing/DHCP teardown errors,
/run/live/persistence unmount failure and watchdog-not-stopped warning. The kiosk
result does not establish those issues resolved, nor image-update compatibility.

## Reproducible startup companion staging

`install-startup.py --rootfs /absolute/staging/root --container CONTAINER`
stages the address waiter and a matching systemd drop-in into an existing rootfs.
The name is explicit, not tied to kiosk-test or a board. The helper is executable;
the drop-in is mode 0644. Staging neither starts a service nor edits native VyOS
configuration, permissions, firewall rules or persistent browser/pairing state.
Symlink destinations and conflicting unmanaged files are rejected before writes.
This is only a packaging primitive: the normal builder does not call it yet.
Changed pre-existing helpers require explicit review instead of silent overwrite.

Live migration must first back up the old helper/drop-in, review their differences,
then install and daemon-reload under administrator control. To roll back, restore
those two backups (or remove the newly installed drop-in and, if no other kiosk
uses it, helper), then daemon-reload. Native container configuration and /config
state stay intact. Do not remove readiness handling on a running installation
without accounting for its explicit address binds at next boot.

2026-09-20 continuation: all 11 experiment tests pass, including arbitrary names,
repeat staging, invalid names, symlink escape rejection and preservation of an
administrator's drop-in. ROCK SSH at 192.168.178.173 returned "No route to host";
no live changes, restart, schema installation or image build performed.

Next: reconnect and inspect installed upstream container/schema behavior before
implementing a dedicated kiosk owner. Preserve one configuration owner for native
containers; do not issue recursive commits from a conf_mode handler or patch CLI
caches manually. Retain native-container controls as the working baseline.

### Live staging and browser recovery follow-up

ROCK returned after user reboot. Zero failed units; NTP synchronized. Early boot
used April 27 before synchronization to September 20, so Podman's initial "Up 4
months" was a wall-clock artifact, not evidence of an old running container.

Installed the reproducible startup companion on the live system after confirming
the existing waiter was byte-identical (SHA256
d4e41e98c6c73dcf7fd17f408d70656d58a68972276fbe50d949488a635c35e1).
Original helper/drop-in backup:
`/config/kiosk-test/backups/startup-1789896867713182172/`.
Installer sources reside under `/config/kiosk-test/startup-package/`, root-owned.
These saved sources allow manual restoration after an update but do NOT install
an automatic boot/update hook. No claim of completed image-update integration.

Container restart at 11:34:39 CEST passed the address precheck; prior desktop
children stopped and Xorg exited 0. Runtime returned 90 degrees, 1080x1920 and
touch event4. Sunshine detected h264_rkmpp. No additional devices/capabilities or
ports were granted. Xorg's inaccessible event2/event3/event6 correspond to
unexposed receiver consumer/system-control interfaces and the board power key;
host udev metadata advertises them but the container cannot open them. Standard
keyboard/mouse and touchscreen nodes are mapped. Hotplug reconciliation remains
open; do not broaden device access just to remove these diagnostics.

Browser crash recovery: targeted SIGKILL of the sole Chromium browser parent
(PID 40) resulted in replacement PID 687 after 2.59 seconds, still running after
another four seconds. Display status retained portrait and touch mapping. The
test used `ps` for process discovery after two read-only /proc discovery attempts
found no candidate (neither attempt sent a signal). This establishes process
recovery, not visual correctness or recovery from a hung page. Sunshine probe
capability/audio and Chromium system-bus messages still require separate review.

## Experimental browser media policy (2026-09-22)

The new source extension adds these native container settings (requires the new
vyos-1x package **and** a companion image advertising media-policy version1):

```text
set container name kiosk-test kiosk video-decode auto
set container name kiosk-test kiosk video-decode software
set container name kiosk-test kiosk video-h264-buffers enabled
set container name kiosk-test kiosk video-av1-buffers enabled
show kiosk media kiosk-test
```

Choose one decoder mode. Buffer settings also accept `disabled`; enabling them
requires explicit `video-decode auto` and an image advertising the corresponding
validated feature. A stock Chromium image is rejected for enabled reserves.
No hardware-required mode is exposed: strict per-stream enforcement has not been
implemented. Graphics rendering, local video decoding and Sunshine encoding are
independent. These controls do not alter profile D or the remote viewer's browser.

Absent nodes emit no new environment variables, preserving existing behavior and
stored configuration. Explicit values persist through native `save`/image updates
provided the target image/package still supports the policy. Commit rejects an
incompatible companion image. Native container lifecycle owns these settings:
a media change currently restarts the **container**, including remote sessions;
Sunshine-only policy changes retain their existing narrower restart behavior.
No rewrite of saved URLs, Sunshine encoder tuning, credentials or pairings occurs.

`auto` permits the browser's codec-dependent software fallback; it does not make
unsupported HEVC profiles playable in software. A root-owned image manifest at
`/usr/share/vyarm/kiosk-media-capabilities.json` binds an opt-in backend recipe to
the SHA256 of the actual browser executable. The runtime enumerates accessible
V4L2 stateless OUTPUT formats, media and render nodes as the kiosk user. It uses
no board names or persistent videoN assumptions. A Wayland-only validated recipe
is not forced into the current X11 kiosk. Missing recipe/devices produces an
explicit fallback reason and preserves browser automatic selection.

Status reports requested policy, device availability, verified runtime and active
features. **Actual per-video decoder remains unknown in this startup report**;
it must come from browser media diagnostics. In the isolated live test, separate
CDP evidence confirmed V4L2 for auto and Dav1d for software/no-device fallback.
A startup probe alone is never marked as confirmed hardware decoding.

The companion `media-cli-20260922` image adds the generic policy to the existing
runtime, but intentionally has no reserve-support labels or hardware recipe for
its stock browser. The tested custom Chromium/Wayland recipe is recorded under
`av1-timeout-cli-20260922/media-capabilities.json`; its `/candidate-p010` path is
specific to that isolated runtime. Packaging a production Wayland/browser runtime
and physical display validation remain separate from these CLI changes.
