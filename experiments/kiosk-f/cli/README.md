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
examples or per-value explanations. Output completes `auto`; hardware-specific
output names are not yet discovered for completion. Rotation completes all four
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
and packaging. It patches container.xml.in/container.py and adds python/vyos/kiosk.py.
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
