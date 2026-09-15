# Tailscale subnet-router profile and native VyOS CLI

The builder prepares an image only when the optional Tailscale subnet-router
profile is explicitly selected. The default is disabled so a base image remains
close to stock VyOS. The profile deliberately does not include Tailscale binaries, credentials,
tailnet identity, advertised routes or board-specific network policy.

Interactive builds ask whether the profile should be enabled. Non-interactive
builds use `TAILSCALE_SUBNET_ROUTER=yes|no`; GitHub Actions exposes the matching
`tailscale_subnet_router` boolean input. When disabled, no Tailscale wrapper,
service, native CLI or readiness command is injected into the root filesystem.
The builder compiles a single matching `vyos-1x` package from source containing
the selected KVM and/or Tailscale extensions. Base builds skip this step.

## Persistent local layout

Install the official static Linux ARM64 binaries later on the running system:

```text
/config/tailscale/
├── bin/
│   ├── tailscale
│   └── tailscaled
└── state/
    └── tailscaled.state
```

The included `vyos-arm64-tailscaled.service` is inert until both binaries are
installed and `service tailscale` is enabled through the native CLI. The
configuration owner creates `/run/vyos-tailscale/config.json` and starts the
service during commit and boot configuration loading. It runs the daemon with its
state and node identity under `/config`, so the identity can survive a normal
VyOS `add system image` update. The `tailscale` wrapper uses the matching socket
at `/run/tailscale/tailscaled.sock`.

When `add system image` asks whether to copy the active configuration, answer
`y`. VyOS then copies the active configuration directory into the new image.
The locally installed binaries, daemon state, node identity and preferences
under `/config/tailscale` are therefore available to the prepared service after
rebooting the new image. Store real files in this directory rather than using
symlinks to files outside `/config`.

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

After installing executable ARM64 binaries, replace the example prefix with
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
`config.boot`, binaries and identity are copied under `/config`. The new image
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
