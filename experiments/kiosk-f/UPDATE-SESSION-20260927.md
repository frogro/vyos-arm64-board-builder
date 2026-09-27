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

## Offline validation fix

Full CLI build completed successfully, including upstream pylint. Initial ISO
assembly stopped correctly on config validation. Isolated reproduction:
`chroot rootfs ipaddrcheck --is-any-single 1.1.1.1` exits2 under QEMU10.2.1
with 'could not allocate memory'; syscall trace shows brk allocation failure.
Same binary and input with QEMU_RESERVED_VA=0x100000000 exits0. Full saved
configuration validates with an empty diagnostic under that environment.
No saved configuration changed. The assembly helper applies this environment
only to offline config validation; native ARM64 runtime is unchanged.
Retained first attempted rootfs and original modules for inspection; re-extracted
pristine A-D squashfs and launched unit vyarm-adf-finish-retry-20260927 to build
from clean base. Inspect finish-image.status/log for current result.

## Installed A-D/F candidate (2026-09-27 08:30 CEST)

- finish-image.status=complete. ISO:
  tmp/adf-update-20260927/output/vyos-999.202609250800-adf-20260927-rock-5b-network-tailscale-kvm-kiosk.iso
  SHA256 e3bb115cfddce6da5274999554a02a23f837f7dafbe2f71d6a781814d0619e6e.
- Copied ISO+checksum to /home/vyos/adf-update-20260927 on ROCK; remote
  SHA256 verification passed. Native installer completed successfully as
  999.202609250800-adf-20260927, NOT default, config+SSH keys copied, history not copied.
  Installer default suggestion still reads underlying rolling base version from
  /opt/vyatta/etc/version; the unique explicit installation name identifies this
  A-D/F candidate. version.json contains candidate name and integration comment.
- Kiosk stopped for consistent config/state copy under10min independent restart
  timer; after installation old kiosk started and verified active, timer stopped.
- Candidate rootfs mounted read-only temporarily for native ARM64 validation:
  full saved config validates, D/F handler owners correct, IP validator succeeds
  without QEMU environment. Root unmounted and temporary mount directory removed.
- cmp verifies current config.boot equals candidate
  rw/opt/vyatta/etc/config/config.boot and all private SSH host keys match.
- Installed files SHA256 match local ISO inputs:
  vmlinuz 0e482366b0ba249defb340ead610d6858329771f07bbca868aaf5c993a0152fe
  initrd 7a161cc8c9151a7527630012ce452f09db9004fcf2808363b0bfcc20c0a23aec
  DTB 706f4321dce85edcf458bc8f237f2cef7f9f72f40297b0cdb63f05fb32f15ec0.
- Old default remains uuid5-9061c446-3e56-58c8-af43-bffd3ea145ca.
- No reboot performed. Missing selected USB inputs still block a clean native
  container config startup; monitor/USB question remains unanswered. Restore
  original selected mappings when devices return, prepare one-shot boot/fallback,
  then test candidate kernel and four codecs. Do not claim decoder live tests
  for this newly installed combination from the offline/native CLI checks.
- QEMU validator regression controls passed: valid IPv4/IPv6 and prefix accepted,
  invalid address and prefix rejected with reserved guest virtual address space.
