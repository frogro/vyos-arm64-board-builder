# Tailscale-ready VyOS ARM64 images

The builder prepares an image only when the optional Tailscale subnet-router
profile is explicitly selected. The default is disabled so a base image remains
close to stock VyOS. The profile deliberately does not include Tailscale binaries, credentials,
tailnet identity, advertised routes or board-specific network policy.

Interactive builds ask whether the profile should be enabled. Non-interactive
builds use `TAILSCALE_SUBNET_ROUTER=yes|no`; GitHub Actions exposes the matching
`tailscale_subnet_router` boolean input. When disabled, no Tailscale wrapper,
service or readiness command is injected into the root filesystem.

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

The included `vyos-arm64-tailscaled.service` is enabled but inert until
`/config/tailscale/bin/tailscaled` is executable. It runs the daemon with its
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

Advertised routes and SNAT mode remain adjustable on the running system with
`tailscale set`. New advertised prefixes may still require approval in the
Tailscale admin console. If VyOS is not the default gateway of the destination
devices, install the `100.64.0.0/10` return route on their actual gateway,
through DHCP or on the individual hosts before disabling subnet-route SNAT.
