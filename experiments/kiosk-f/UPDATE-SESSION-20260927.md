# A-D foundation plus F update, 2026-09-27 (in progress)

User authorized download, installation on ROCK, F integration and testing.
Isolated branch integration/adf-update-20260927 merges current F (2fb6b80)
with tested A-D branch (63767ef), without changing main or publishing.

## Confirmed

- Actions36267716867 succeeded; downloaded candidate SD/ISO and both supplied
  SHA256 checks passed. Base999.202609250800, kernel6.18.50-vyos,
  vyos-build d1394291337eb0274e026145a4c6245207c1c71d,
  vyos-1x4e3e38a2e665bb2d8e9446116e02300bb38a2ab4.
- Native A-D ISO installed as999.202609250800-ad-test, copied configuration
  and host keys, NOT selected as default and NOT booted.
- Existing live F installer lacked board-DTB patch. Saved original under
  /home/vyos/adf-update-20260927/image_installer.before.py and applied the
  builder's generic patch. Copied exact verified A-D DTB to the installed
  image's dtb/rockchip/rk3588-rock-5b.dtb; hash
  9ffb614c8aa6442f18ca4c6838f0c631307b3da0124385a4b7ccc7e774e2a4e4.
- Consistent /config and SSH backup with kiosk stopped, on ROCK and independently
  in local tmp/adf-update-20260927/private-backup (private, never commit).
- Restart revealed disconnected configured ILITEK USB inputs. Both missing
  by-id AddDevice lines omitted ONLY from transient /run Quadlet, original at
  /home/vyos/adf-update-20260927/quadlet-before.container. Saved configuration
  untouched. Container active again; HDMI connected, no USB input currently.
  User asked whether monitor USB is connected; answer pending. Restore selected
  mappings once devices return. Do not claim touch tested or restart with an
  unreviewed missing-device configuration.
- F kernel completed on NUC /var/tmp/vyarm-adf-20260927: immutable copy of
  validated F source, replace legacy RGA experiment with consolidated D patch;
  reused compilation cache, preserved original source and previous artifacts.
  Full Image/modules/DTB plus all8 OOT modules built against current VyOS source.
  1731 modules, complete output at local tmp/adf-update-20260927/kernel-artifacts.
- Runtime exported from verified image3b7a84a541ae1b766062167ef3a598b20609a345df3a7b8c5fef0b73fa800fb8,
  tag localhost/vyarm-kiosk:wayland-user-20260926. Archive SHA256
  caa57b4360f1874938a7f0dd32e0b44ce6f005c668f4b0e15384489b8eca7985,
  image config digest checked against ID. No persistent browser/user state in archive.
- 81 F tests passed; native CLI preparation8, host fixes3, KVM CLI10,
  board-DTB update8, image table formatting5 passed.

## Still running / next

- Matching full D/F CLI package builds locally in isolated cached ARM64 build
  container under QEMU, tmp/adf-update-20260927/run-cli-build.sh and build.log.
  CPU limited4, memory4GiB/swap6GiB. Current clean source prepared with generic
  prepare-vyos-1x-profile.py; upstream requires new OCaml dependencies.
- Assemble from extracted immutable A-D ISO root with update/assemble-from-ad.sh,
  complete matching kernel, new CLI and verified runtime. Helper also reapplies
  image-name, CPU-display and DTB updater patches after package replacement.
- New package/rootfs/native CLI cache and preserved config validation, complete
  ISO hash audit required before installation. A-D/F not yet assembled/installed.
- Native install unique A-D/F version, old default retained, protected boot,
  live backend/decoder/D tests and configuration comparison still pending.
- No reboot performed this turn. No main push or publication. No old artifacts
  deleted to free space; NUC new workspace uses separate root filesystem.

## Continuation checkpoint

- CLI compilation reached full upstream pylint stage; four active workers,
  no failure reported as of this checkpoint. Native build exec session99787;
  status/log in tmp/adf-update-20260927. Do not start another package build.
- Started local systemd unit vyarm-adf-finish-20260927. It waits for successful
  CLI completion, validates package and executes assemble-from-ad.sh; it does
  NOT install or reboot the ROCK. Inspect finish-image.status/log and unit.
  Maximum wait2h, failed steps stop with statusfailed. No background observer
  or recurring automation created.
- Assembly helper additionally checks preserved config against the generated
  reference tree using a temporary /run tmpfs copy, absent from packaged root.
- ROCK old kiosk still active, saved config SHA256
  4ea89b238f5d043e9c2ca9ad639d14cdd5c19c13f2dc3920fcc2f194d00ae860.
  USB enumeration shows root hubs and Terminus hub, no ILITEK/Logitech devices.
  HDMI reports connected but kernel logged I2C/ELD/EDID errors on kiosk restart.
  User's monitor/USB question remains unanswered. No new-image boot attempted.
- When pipeline finishes, audit ISO and install alongside old default; first
  resolve missing saved USB device mappings before protected reboot/live tests.
