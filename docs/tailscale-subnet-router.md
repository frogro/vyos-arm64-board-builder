# Tailscale subnet-router profile and native VyOS CLI

## Agreed target design — 2026-09-15

The following design was agreed with the project owner. It supersedes the
earlier manual binary-installation approach. Image bundling is implemented;
the explicit manual update command is still planned.

- Selecting profile C (Tailscale subnet router), including combined profiles,
  installs the official ARM64 Tailscale programs and service into the image.
  Base images remain unaffected. Preinstallation does not activate the service,
  authenticate a device or advertise any subnet.
- Follow native VyOS configuration and operational command conventions. Enable
  and configure through `set service tailscale ...`, apply with `commit` and
  persist with `save`. Build the CLI from vyos-1x source for selected profiles;
  do not modify generated CLI caches on deployed systems.
- Keep program binaries and service definitions in the image. Keep user
  configuration in `/config/config.boot` and node identity/authentication state
  under `/config/tailscale/state`. Old binaries copied under `/config` must not
  silently override the programs supplied by a newer image.
- Each normal build with this profile must check the official stable release,
  verify the selected ARM64 download and record its exact version and checksum
  in build provenance. A newer image supplies its build-selected Tailscale
  version. This means current at build time, not an automatic update at boot.
- No unattended Tailscale self-update. Provide an explicitly invoked operational
  command, `request tailscale update`, for a manual update. This is a planned
  command, not an existing command or a `set` configuration leaf. Its detailed
  design must cover verification, recovery after failure and precedence on the
  next image update so an old manual installation cannot mask the new image.
- `request tailscale login` performs interactive authentication; `show tailscale`
  reports status. No reusable auth keys or preauthenticated identity belong in
  a distributable image. Subnet approval and tailnet access policy are separate
  from device login. A Photobooth Funnel or its address is not required.
- When upgrading to another image with profile C and retaining configuration,
  settings and node identity must survive. Validate this with an actual image
  update, reboot, reconnection, subnet access and rollback test before claiming
  end-to-end update compatibility. Future upstream compatibility is not implied
  merely by downloading the newest release.

Implementation follow-up: validate the ARM64 package/image builds and complete
live update tests; implement the explicit update operation after the normal
image-update path is verified.

## Image implementation

The builder prepares an image only when the optional Tailscale subnet-router
profile is explicitly selected. The default is disabled so a base image remains
close to stock VyOS. The profile includes verified official ARM64 binaries but
no credentials, tailnet identity, advertised routes or board-specific policy.

Interactive builds ask whether the profile should be enabled. Non-interactive
builds use `TAILSCALE_SUBNET_ROUTER=yes|no`; GitHub Actions exposes the matching
`tailscale_subnet_router` boolean input. When disabled, no Tailscale wrapper,
service, native CLI or readiness command is injected into the root filesystem.
The builder compiles a single matching `vyos-1x` package from source containing
the selected KVM and/or Tailscale extensions. Base builds skip this step.

## Programs and persistent state

The normal build queries the official stable release metadata and downloads the
ARM64 static archive over HTTPS. It checks the published SHA256, validates both
ELF binaries as ARM64 and installs them under `/usr/libexec/tailscale/`. Only the
two expected regular files are read from the archive; arbitrary tar paths are
not extracted. Download or validation errors fail the build. Provenance is saved
at `/usr/share/vyos-arm64-board-builder/tailscale/build.json` and the version and
archive checksum are printed in the build log. The installer supports an explicit
`--version` for reproducible rebuilds while still recording the current stable
version; normal board builds select the latest stable version.

The bundled service remains inert until `service tailscale` is enabled through
the native CLI. On commit and boot configuration loading, the configuration
owner creates `/run/vyos-tailscale/config.json` and starts the service. The wrapper
and service always use image-owned binaries, never old `/config/tailscale/bin`
copies. The state file remains `/config/tailscale/state/tailscaled.state` and the
socket remains `/run/tailscale/tailscaled.sock`. User settings live in
`/config/config.boot`. No unattended self-update is enabled; the native owner
explicitly sets `--auto-update=false`.

When installing another image with this profile, retain the active configuration.
The settings and node identity are copied under `/config`, while the programs come
from the new image. The existing files under `/config/tailscale/bin`, if any, are
ignored rather than deleted. Actual identity retention and rollback across
versions must still be validated on hardware.

Run the read-only readiness audit with:

```text
sudo vyos-arm64-tailscale-readiness
```

## Configuration boundaries

Enable forwarding through VyOS configuration rather than unmanaged files under
`/etc/sysctl.d`. Choose advertised subnets locally after installation and
approve them in the Tailscale admin console. Do not store reusable auth keys in
the image or in shell scripts.

Start with Tailscale's default subnet-route SNAT. Disabling SNAT requires a
return route for `100.64.0.0/10` through the VyOS LAN address. Tailscale and
VyOS both interact with netfilter, so firewall reload behaviour must be tested
before using a non-default netfilter mode or deploying the appliance in
production.

Advertised routes and SNAT mode are owned by `service tailscale`. Manual
`tailscale set` changes to these preferences are overwritten on the next commit
or daemon restart. New advertised prefixes may still require approval in the
Tailscale admin console. If VyOS is not the default gateway of the destination
devices, install the `100.64.0.0/10` return route on their actual gateway,
through DHCP or on the individual hosts before disabling subnet-route SNAT.

## Native configuration

On an image containing profile C, replace the example prefix with
the actual subnet that should be reachable through this router:

```text
configure
set service tailscale advertise-route '192.0.2.0/24'
commit
save
exit
request tailscale login
show tailscale
```

Authentication is an interactive operational action, never a build or commit
action. No reusable auth key is stored in `config.boot`. Advertisements still
need tailnet approval and access policy. IPv4 and IPv6 prefixes are accepted;
default routes are rejected because exit-node support is outside this feature.
Forwarding, VyOS firewall rules and tailnet access controls need separate tests.

Optional settings:

```text
set service tailscale accept-routes
set service tailscale disable-snat
set service tailscale netfilter-mode 'on'
```

By default, acceptance of other devices' routes is off, subnet SNAT is on,
and netfilter mode is `on`. `nodivert` and `off` require explicit local firewall
integration. Tailscale DNS acceptance is always disabled so VyOS retains
ownership of resolver configuration. Other Tailscale preferences are not reset.

Deleting an `advertise-route` clears it from the daemon. `set service tailscale
disable` or deleting `service tailscale` stops the daemon but retains binaries
and identity. Re-enabling starts the existing identity. Preferences are also
reapplied by `ExecStartPost` after a daemon restart.

## Update and migration boundary

Between native-CLI images, retain the configuration during image installation:
`config.boot` and identity are copied under `/config`. Programs come from the new
image. The new image
must also include the Tailscale profile. Boot reconstructs runtime configuration.
Keep the previous image until reconnection and subnet access are verified.

Older Tailscale-ready images did not have this configuration node. Before moving
from a manually managed installation, record its advertised prefixes, route
acceptance, SNAT and firewall settings. On the first native-CLI image, configure
the corresponding `service tailscale` settings using local or independent SSH
access. Existing identity is retained, but the old daemon preferences are not
silently imported into VyOS configuration. Do not perform this migration with
Tailscale as the only management connection.

## Validation status — 2026-09-15

Local tests cover independent/combined profile source preparation, prefix
validation, explicit preference removal, disabled service lifecycle and identity
file preservation. XML definitions validate against upstream VyOS schemas.
An isolated Tailscale 1.102.4 userspace daemon accepted IPv4/IPv6 preference
updates and their removal before login, remaining in `NeedsLogin` state.
This local test used the official AMD64 binary on the development PC; it does
not validate ARM64 routing or kernel netfilter behaviour.

Pending: source-built ARM64 package matrix, image installation, boot and
rollback, interactive tailnet login, actual subnet traffic, firewall reload,
SNAT/return paths and identity retention across an image update. The already
running ROCK build at commit `4becb3a` predates this native Tailscale CLI.

### Bundling and CLI generation follow-up

The official Tailscale 1.102.4 ARM64 archive was downloaded and validated locally
(SHA256 `9dd1e6a592a014bbaea0103167ffe299adeda4ba14e078ce9c2895364f6c4c3f`).
Installer tests cover bad checksums, wrong architecture, symlink rejection,
profile gating and preservation of node state. Native operational XML now
supplies help for its top-level `show`/`request` nodes: the upstream generator
otherwise writes empty `node.def` files and fails the ARM64 package build.
The same correction applies to KVM `show`. Local upstream-generator checks pass;
the updated ARM64 CI and complete live image lifecycle remain to be verified.

## Access control and deployment permissions

See [the access-control review](access-control-review.md) for the native VyOS
permission policy, observed listeners, Tailscale/firewall interaction and
remaining acceptance tests. Network access is configured by the deploying
administrator; this profile does not add a separate web role system.
