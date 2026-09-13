# VyOS-native integration: required correction and remote compatibility

Status: open, recorded 2026-09-13 at the user's request. This is a project-wide
design requirement: use VyOS configuration, packaging, service lifecycle,
validation, persistence and update mechanisms wherever possible. Current release
candidates remain unchanged; this document does not claim completed migration.

## Required correction

Move the KVM XML interface definition and conf_mode implementation into the
matching VyOS-1x source/package build. Let the normal VyOS generators produce
node.def, reftree.cache, the Python reference metadata and configd inclusion
consistently. Retire handwritten duplicate CLI nodes and post-build reference
merging after equivalent behavior has been demonstrated. Pin the matching
VyOS-1x source/package provenance; a vyos-build commit alone does not attest
all packages pulled from a moving package repository.

Preserve the existing public configuration paths and get_config -> verify ->
generate -> apply contract. Keep board-specific hardware detection behind
providers. Audit console-speed schema patches and image-manager/GRUB wrappers
for the same source/package integration goal. Firmware boot differences still
require provider implementations; native integration does not mean pretending
all boards use EFI.

## Findings from the current code (static review, not live API acceptance)

- install-kvm-cli.sh installs CLI node definitions and conf_mode. The reference
  merger updates reftree.cache, vyos.xml_ref.cache and configd-include.json.
  It verifies owner and priority in a fresh Python process. Thus KVM is not
  intentionally limited to an interactive shell.
- service_kvm_over_ip.py reads VyOS Config/get_config_dict and uses
  get_config/verify/generate/apply. Runtime artifacts are generated from that
  configuration. Changed-node detection avoids unrelated gadget restarts.
- SSH CLI and generic set/delete-based automation should use those same paths.
  HTTPS /configure and /config-file perform normal configuration commits;
  /retrieve reads configuration. Compatibility is plausible from this design,
  but no end-to-end API/SSH/save/reboot/rollback test of the new image has been
  performed in this task. Do not mark it certified compatible.
- Dedicated third-party resource modules, GUIs and schema-driven clients may
  not know the custom service kvm-over-ip subtree. Generic command/path support
  is distinct from dedicated feature support. No NETCONF or other untested
  protocol support is claimed.
- Tailscale intentionally remains optional preparation. The image contains no
  Tailscale binaries or credentials; installation and activation are the user’s
  decision. This is an accepted scope boundary, not an integration defect. After
  user installation there are persistent binaries/state/preferences
  under /config, not a complete declarative VyOS conf_mode integration. A
  config.boot export alone is not a complete Tailscale backup. KVM virtual-media
  files likewise remain external assets referenced by configuration.
- The console and image lifecycle extensions must be checked through both CLI
  and remote entry points. HTTP /image handling must reach the same guarded
  provider path as local add/delete system image.

## Acceptance before calling the correction complete

On an isolated test system with the feature profile present, verify:

1. CLI over SSH and HTTPS /configure set/delete equivalent KVM subtrees;
   /retrieve and CLI output agree. Exercise valid and invalid input.
2. Batch multiple required fields in one API transaction; verify commit failure
   returns an error and leaves committed configuration unchanged. Test actual
   runtime recovery separately: a failed apply is not proof of automatic rollback.
3. Save, load/merge and reboot restore the service state. Delete removes the
   intended runtime configuration. Repeat identical operations for idempotence.
4. Commit-confirm/rollback and competing remote sessions follow VyOS semantics;
   verify both config state and video/gadget runtime after recovery.
5. Test generic remote automation; record client/version and avoid claiming
   dedicated KVM support in tools which lack its schema.
6. Test board-matched image add/delete/default selection via supported CLI/API
   paths, then boot the selected version and verify configuration persistence.
7. Keep Tailscale preparation-only: no bundled binaries, automatic installation,
   login or predefined advertised routes. Add the planned optional native CLI
   described below as part of preparation. Verify the
   prepared unit remains inert without user-installed binaries, and document
   user-controlled activation, persistence and external-state backup. Validate
   coexistence with VyOS firewall/routing after optional installation.

Source references checked 2026-09-13:
- https://docs.vyos.io/en/rolling/automation/vyos-api.html
- https://docs.vyos.io/en/rolling/configuration/service/https.html
- https://github.com/vyos/vyos-1x

Historical rationale: Vyos latest PDF, pages 356-357. Repository evidence:
tools/install-kvm-cli.sh, tools/kvm-cli/merge-vyos-reference.py,
tools/kvm-cli/service_kvm_over_ip.py, docs/tailscale-subnet-router.md.

## Agreed next stage: optional native Tailscale CLI

Recorded 2026-09-13 following the user's clarification: a native VyOS CLI is
part of the desired preparation, even though installing Tailscale itself remains
optional. The current image has a shell wrapper and prepared service, not this
new configuration CLI. Implement after hardware acceptance of current candidates.

Start with a small, explicitly defined schema using the normal VyOS-1x XML and
conf_mode build mechanisms. Planned scope: enable/disable the service, advertised
subnets and selected routing options, plus operational commands showing installed,
authenticated and connected state. Exact command paths are not yet decided.
Persist managed settings through VyOS configuration and test the same settings
through SSH and the HTTPS API, including save/load, reboot and rollback.

Do not bundle Tailscale binaries or credentials. Installation and authentication
remain separate user decisions; commit must not download software or launch an
interactive login. Without binaries, keep the service inactive and provide clear
validation/status messages for activation attempts. Do not store plaintext auth
keys in configuration.

Define which settings VyOS owns and how direct tailscale set changes are detected
or reconciled. Test firewall reloads, routing, SNAT and rollback so Tailscale and
VyOS do not overwrite each other's intended state. Preserve identity separately
from declarative configuration and document its backup/update handling.
