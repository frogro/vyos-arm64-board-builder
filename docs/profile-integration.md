# Optional profiles on main

All supported profile sources now live on `main`. Automatic Rolling builds and
Community repository update channels remain A–B (`network`). Installing a source
change does not enable an application on an existing router.

| Profile | Content | Selection |
| --- | --- | --- |
| A | Board kernel, firmware, DT and boot support | Always |
| B | Additional network/Wi-Fi/BT/modem support | `extended_network` |
| C | Tailscale and subnet router | `tailscale_subnet_router` |
| D | KVM capture and board-specific USB HID | `kvm_over_ip` |
| F | Chromium kiosk and Sunshine | `kiosk_f` |
| G | Miracast, AirPlay, Moonlight, Steam Link receivers | `receiver_g` |

The flags are independent. A–B, A–B–C, A–B–C–D, A–B–C–D–F and
A–B–C–D–F–G are cumulative examples, not separate branches. Selecting G does
not enable F or C/D. Selecting F or G includes its shared graphics dependencies;
selecting D alongside either also builds the optional cached-copy helper.
Services still require explicit runtime configuration.

F/G builds currently support ROCK 5B and Orange Pi 5 Plus. Other boards are
rejected until their multimedia paths have been integrated and tested. Board
routing remains separate: ROCK uses its supported USB-A gadget path
`fc400000.usb`; Orange Pi uses its USB-C gadget path `fc000000.usb`.

F/G runtime builds retain the checksummed bootstrap inputs from
`adf-compare-inputs-20260927`; the hashes are in
`experiments/kiosk-f/ci/inputs.sha256`. Only userspace assets are extracted,
never the archived ROCK kernel or DT. G receives a stripped, flattened graphics
base without Chromium/Sunshine. This is a build dependency, not an installed
F profile. GStreamer/FFmpeg receiver patches stay in G userspace; board decoder
and DMA-heap prerequisites belong to A.

The native CLI is rebuilt from the original image's exact VyOS-1x source when
an optional CLI extension is selected. An A–B build does not install these
extensions or their multimedia containers. Kernel drivers available in A do not
imply that an application is running.

## Validation and release boundaries

Selection tests cover every combination of the five optional flags. Native
source checks additionally cover cumulative and standalone F/G combinations.
F/G image assembly verifies selected and excluded payloads, source provenance,
and board gadget routing before creating the ISO. Unit/source checks are not
hardware tests or proof that every combination has booted.

A–B publishes to its registered Community repository and update channel. Full
images must not use that channel: the existing profile identity check prevents
an automatic downgrade to A–B. Keep the previous bootable image until a new
image and configuration have been verified.

Hardware acceptance order for this integration:

1. Orange Pi 5 Plus: fresh A–B installation, CLI/login, Ethernet, optional
   Wi-Fi/BT, helpers and a subsequent update using its Community channel.
2. ROCK 5B: the same installation/update checks with its board boot path.
3. Raspberry Pi 5: the same checks with its own boot/update provider.

F/G functionality must subsequently be checked in an image that selects those
profiles. The established test-branch commits remain available as reference;
`cf481dc2421b77e4ef4df2266c0f11a9394664ee` is the main revision before this
integration. Reverting source commits is distinct from selecting an older
installed image at boot.

## Missing Rolling kernel packages

A reusable raw artifact must match the selected immutable VyOS source and the
raw-build recipe. When a fresh base is needed, the builder first checks the
signed ARM64 package index for the exact `kernel_version`/`kernel_flavor` from
that source. It downloads and verifies an available package before live-build.
If the verified index no longer contains it, the official kernel package recipe
from the same source runs on an ARM64 runner. Repository/signature failures do
not trigger a silent fallback or a kernel version change.

The resulting package is checked for package name, ARM64 architecture, kernel
payload, source commit and SHA-256 before it enters `vyos-build/packages`.
Board-specific kernels, drivers, modules, DTs and selected application profiles
are still assembled separately; sharing a base does not share a board kernel.

`Rebuild Community A-B images from one fresh base` creates the base once, then
dispatches the four board publications with its attested artifact. Existing
releases remain available. Fresh base creation produces a new image version,
so old releases do not need to be overwritten merely to pick up builder fixes.
