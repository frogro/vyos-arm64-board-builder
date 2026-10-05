# Native container kiosk extension (source prototype)

This is an opt-in vyos-1x **source** extension, not an installed live command and
not yet a selectable builder profile. Keep upstream container.py as the sole
owner of lifecycle, native configuration persistence and API configuration.
There is no separate `service kiosk` owner or recursively committed shadow tree.
Administrative configuration permissions remain native VyOS permissions.

Target commands, available only after building/installing the extended package:

```text
configure
delete container name kiosk-test environment KIOSK_URL
delete container name kiosk-test environment KIOSK_OUTPUT
delete container name kiosk-test environment KIOSK_ROTATION
set container name kiosk-test kiosk url 'file:///opt/kiosk/input-test.html'
set container name kiosk-test kiosk output 'auto'
set container name kiosk-test kiosk rotation '90'
commit
save
exit
```

Remove only environment nodes that exist. Preview the candidate before commit.
The current live system still uses those environment nodes; do NOT migrate it
until the package/schema is installed. Existing device, image, network, port,
volume and enable/disable settings remain native container configuration. The
extension grants no additional permissions or hardware access. A compatible
kiosk image is required; arbitrary container images need not consume these vars.

CLI help follows upstream English wording: every kiosk leaf includes value help,
examples or per-value explanations. Output completion queries the selected running
kiosk's X11 server with a two-second timeout and offers connected output names
plus `auto`. A stopped/unavailable container yields `auto`; it is never started
by completion. No DRM-to-X11 naming assumptions are made. Rotation completes all four
supported values. URL help distinguishes container paths from host paths. Help
must accompany future options, including defaults, prerequisites and valid values.

Validation runs in the native container verify phase, before generation/apply:
URL required, http/https/absolute local file only, no embedded user/password,
no raw control/space/double-quote/backslash characters, valid port, rotation
0/90/180/270 and syntactically valid output. Query strings can contain percent
escapes and literal dollar signs; generated Quadlet escapes systemd substitution.
An actual connected display can only be validated by the desktop at runtime.
Defaults with a kiosk node: output auto, rotation 0. No kiosk node leaves existing
container behavior unchanged, including legacy KIOSK_* environment settings.
Conflicting legacy settings are rejected when the new node is used.

## Build path and tests

Run `python3 prepare-source.py /path/to/clean/vyos-1x` BEFORE upstream generation
and packaging. It patches container.xml.in/container.py and adds python/vyos/kiosk.py
and src/completion/list-kiosk-outputs.py.
The patch checks exact insertion points and refuses unexpected/already modified
sources. Rebuild via upstream targets, including schema validation, command
templates and reference caches. Do not copy individual node.def files into the
live router or edit its CLI caches. The normal builder has not been wired to this
experiment; a properly versioned package, install/rollback and API tests remain.

2026-09-20 checks:
- 16 experiment unit tests passed.
- Original VyOS build-command-templates accepted the expanded container XML
  against interface_definition.rng and generated the new kiosk subtree.
- Executed the real upstream generate_quadlet_options function before/after
  patching: unrelated minimal container output unchanged; kiosk variables added.
- ROCK Quadlet dry-run preserved escaped percent/dollar values in ExecStart.
- An isolated temporary systemd oneshot running only printf confirmed literal
  `%20` and `${HOME}` survive expansion. It was removed after the test. A prior
  systemd-run probe treated percent escaping differently; unit-file test is the
  applicable evidence for generated Quadlet units.
- No new schema/package installed live; existing kiosk remains on native env CLI.

Local test dependencies and generated files live under the development disk's
tmp/kiosk-cli-* paths, not the root filesystem build directory. lxml 6.1.3 was
installed into a dedicated test venv only, not into VyOS or the ThinkPad system.

## Rollback boundary

Before returning to an unextended vyos-1x/image, replace the kiosk node with its
equivalent three KIOSK_* environment nodes in one native commit/save. Older
packages do not understand the new node. Pairing/browser state remains under
/config. This migration and an actual image update are not yet tested.

## Dynamic output completion test

2026-09-20: 20 local tests pass. The completion helper executed read-only on ROCK
for kiosk-test and returned `auto HDMI-1`. The kernel advertises HDMI-A-1 instead,
confirming why direct sysfs names are unsuitable for this X11 setting. Tests cover
disconnected connectors, timeout, stopped/missing containers and invalid names.
Source preparation and native schema/template generation passed. Completion uses
the native `$VAR(../../@)` context to select the enclosing container name, with
the upstream native-name constraint plus defensive argument validation. End-to-end
Tab/? with that context still requires package installation and remains untested.
No sudo rules, operator roles, host listeners or running display settings changed.

## Native package live test (2026-09-20, 13:50 CEST)

Installed ARM64 vyos-1x version
`999.0-14924-g27383e4f1+kvm-tailscale.e1a4f68a2e90+kiosk.72cc8e8c3d84`
over the matching original base/profile. Original package was reconstructed with
unmodified dpkg-repack 1.54build1 (helper only, not installed) and inspected before
testing. Backup and manual rollback instructions are on ROCK under
`/config/kiosk-test/backups/cli-package-20260920/` (root-only).
Full package downgrade has not been tested.

Package maintainer postinst is identical to the installed one. Existing package
file hashes differ only for container.py, three generated reference caches,
profile provenance and one IPv6 help string. KVM/Tailscale files are retained.
`dpkg --audit` is empty after installation. Postinst emitted an existing-image
cloud-init-local.service missing-dependency warning; installation exited zero.

Live results:
- Actual interactive Tab completion offers `auto` and connected `HDMI-1` with help.
- Invalid rotation 45 is rejected by CLI validation.
- Migrated only three legacy environment nodes into native kiosk url/output/
  rotation using interactive compare, commit, save. Saved whole-config diff
  contains only that migration. Values remain local test page, auto, 90.
- Container restart completed; Xorg previous instance exited zero. New service
  is active, NRestarts=0, display status HDMI-1/90/1080x1920, touch event4 mapped.
- Sunshine startup detects h264_rkmpp. Existing capability/audio-daemon probe
  errors remain; this test did not modify Sunshine or claim to fix those.
- No additional failed service; pre-existing modem recovery failure unchanged.
- This is runtime/state verification, not a new visual/touch confirmation or an
  image-update/boot test. Sunshine CLI and H.265 remain separate pending work.

Test-harness correction: native script-template command wrappers did not return
expected shell failure status for invalid `set`, and plain `exit 1` invokes a CLI
command. Initial automated candidate was discarded and no changes committed.
Testing continued in a fresh interactive session; no pass claim is based on that
script's exit code. Rollback is documented as explicit interactive commands,
not the discarded automated script.

## Optional GPU rendering (source addition, 2026-09-21)

The next package adds `set container name <name> kiosk graphics auto|software`.
Default remains software. `auto` requires the updated startup/helper image and
explicit native container grants for the appropriate render device. The CLI
itself grants no devices and does not pick boards or GPUs. Help/completion lists
both values; incompatible legacy KIOSK_GRAPHICS overrides are rejected.
Absent graphics settings generate no additional environment entry, preserving
existing container behavior. Configuration persistence uses native commit/save;
startup writes only runtime Xorg configuration, never saved values. The startup
and fallback have been live-tested; this new CLI leaf still needs package/schema
build and live CLI validation before use on the router.

### Host devices (2026-09-27)

For native kiosks with `video-decode auto`, device generation queries V4L2
capabilities and compressed OUTPUT formats and supplements the configured
mappings with request decoders plus each decoder's own media controller.
Discovery uses capabilities, not board names or fixed video numbers. Capture,
RGA and encoder-only nodes are not automatically granted. Explicit mappings
remain unchanged; conflicting destinations are rejected. No automatic discovery
is performed for other containers or software/legacy decoding. No buffers or
streams are started by discovery. Rendering devices remain explicitly selected.

Stable selected `/dev/input/by-id` or `by-path` evdev mappings may be absent.
The generated Quadlet retains them as `# KioskInput=` metadata; the input
reconciler removes absent mappings and restores them after reconnection, with
its existing debounce/commit-lock protection. This never edits saved config or
selects arbitrary new USB devices. Other missing device sources remain errors.
Older Quadlets without metadata keep their original fail-closed behavior.

## Bundled runtime selection on ISO update

Containers with native `kiosk` settings and a builder-generated image reference
(`localhost/vyarm-kiosk:github-<run-id>`) use the kiosk runtime bundled with the
currently booted ISO. Resolution happens before native image verification and
Quadlet generation, on boot and on configuration commits. The saved reference,
media, state volumes and display/remote settings are not rewritten. Consequently,
booting a previous ISO selects that ISO's own runtime again. Candidate and
effective configuration are resolved equally so remote-only changes retain their
existing no-restart behavior. Custom image tags remain explicitly pinned.
A missing or invalid bundled manifest fails configuration validation instead of
silently retaining an obsolete runtime.
