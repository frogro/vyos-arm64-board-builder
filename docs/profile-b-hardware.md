# A board hardware and B network coverage

## Ownership

Profile A owns the board boot chain, Device Tree, kernel, physical hardware
capabilities and associated firmware. Exact overrides are selected by
`lib/board-hardware.sh` and stored in `profiles/base-hardware/`. DT-derived
hardware and model requirements still apply to every board, including Raspberry
Pi 5 and E52C. Unknown boards do not inherit Orange Pi or ROCK routing.

Profile B retains additional Ethernet/WLAN/WWAN support and its companion
Bluetooth additions (`profiles/b-hardware/bluetooth.config`). The optional
Orange Pi R6 RTL8852BE PCIe/USB card belongs to B. Its PCIe/USB host interfaces
belong to A. A may preserve drivers already selected by upstream VyOS or by
physical board discovery; profile separation is not a blacklist of those drivers.

Optional non-network peripheral requests (I2C/spidev, USB gadget functions,
IR, Type-C DP altmode) moved from the network catalog to A. Their resolver
retains fail-soft, no-capability-downgrade behavior. Network and BT requests
remain otherwise identical. A now provides generic capture/gadget kernel
capabilities; D still validates those capabilities and enables the application.

## Board-specific scope

- Orange Pi 5 Plus: all former B hardware requirements, readiness checks,
  Panthor firmware roots and peripheral patches apply with or without B.
  This includes USB-C/DP/audio, GPU/NPU/VPU/RGA, camera/ISP and gadget modules.
- ROCK 5B: existing RK3588 capture/MPP/RGA and dual-role kernel requirements
  formerly selected by D are now available in A. The D-only USB-A routing
  overlay and runtime gadget activation remain D-only and ROCK-only.
- Raspberry Pi 5: existing model requirements and native firmware boot handling
  remain in A. E52C retains its existing DT-derived board requirements in A.
  Neither receives RK3588 kernel patches from the exact-board registry.

A supplies drivers, not automatic peripheral configuration. Camera DT graphs
remain sensor-specific; services, receiver applications, media userspace and
profile-specific port-role activation remain in C/D/F/G. Existing feature
requirements can still request the same kernel capability: identical values
are deduplicated, m/y resolves to y, and contradictory disabled/enabled values
fail before compilation. The shared RK3588 patch set is applied once.

## Build, firmware and update compatibility

Readiness checks use the actual Kbuild .config after olddefconfig. Board firmware
roots are passed to the existing module-closure staging code regardless of B.
The staging directory keeps its historical network-firmware name, so both the
SD/eMMC assembler and the update-ISO builder consume the same payload.
Board identifiers, boot providers, release names, profile IDs and update-channel
compatibility are unchanged. Repositories still publish A/B images as `network`.
No installed configuration is migrated or rewritten by this refactor.

Before this refactor: main fdd20d2. Revert the refactor commit for source rollback;
retain the installed working image for device rollback. Existing builds use
their pinned commit. This source migration does not replace their artifacts or
restart them. Full rebuilt-image boot validation remains required.

## Evidence and limits

Board inventory uses pinned kernel/DT sources and checked-in requirements, not
live manufacturer-page scraping. Tests cover exact board selection independent
of B/D, retention of the optional Wi-Fi/BT scope, requirements and firmware
selection. Module availability does not prove physical display/camera/NPU use.
The hardware-specific acceptance notes in docs/hardware remain applicable.

## RK3588 DMA heaps belong to base A

ROCK 5B and Orange Pi 5 Plus provide system and CMA DMA heaps in base A.
These are shared kernel allocation interfaces used by GPU/video/RGA consumers
in D/F/G, rather than network or application features. Linux 6.18 offers the
heap switches as bool, so they are built in; the application profiles still
control device access and service activation. The board readiness check rejects
a generated kernel configuration missing either heap or its CMA dependencies.
This also applies to A/B images without any running multimedia services.
