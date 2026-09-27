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

## Protected native boot and decoder comparison (2026-09-27 morning)

- Booted installed candidate with a self-clearing GRUB one-shot override and
  independent 15min monotonic return timer. Old default stayed unchanged.
  Candidate config temporarily omitted ONLY two absent ILITEK input mappings,
  with original in shared boot/vyarm-adf-test-20260927/config.original.
- Native candidate started Wayland/Weston DRM, 90-degree rotation, sandboxed
  custom Chromium as kiosk user. No failed systemd units. Status CLI works;
  Sunshine reports disabled as configured (no streaming session tested).
- Important regression: saved numerical device mappings passed video2/3/5,
  but this boot enumerated rkvdec as video0, HDMI RX as video2, RGA as video3,
  AV1 as video5. First probe: H264 software FFmpeg, VP9 software Vpx,
  HEVC unsupported; AV1 hardware V4L2. This was device passthrough, not a missing
  Chromium patch or decoder kernel failure.
- Added video0 ONLY to transient /run Quadlet, restarted and repeated exact
  fixtures using same kiosk UID/device groups and existing policy flags.
  All four reached EOS using V4L2VideoDecoder, kIsPlatformVideoDecoder=true:
  H264 High 1080p60 2/600 dropped; HEVC Main10 1080p60 3/300;
  VP9 profile0 1080p60 9/300; AV1 Main 1080p60 8/300.
  These 5–10s smoke tests prove hardware selection and EOS for these fixtures,
  not sustained zero-drop playback or all streams/profiles.
- Test browser used CDP pipe and loopback-only fixture server; no sandbox
  disabling. Normal browser resumed after each probe. No matching decoder
  timeout/IOMMU fault/panic observed; HDMI EDID/I2C/RGB sink warnings remain.
  Physical display quality and touch NOT confirmed (USB inputs still absent).
- Structured comparison: adf-decoder-results-20260927.json. Full raw local
  tmp/adf-update-20260927/decoder-results{,-correct-device}.tar. Shared ROCK
  boot/vyarm-adf-test-20260927 holds fixtures, results, kernel log and backups.
- Restored candidate config byte-for-byte and original menu. Removed temporary
  one-shot hook and future return timer activation. Requested return to old
  unchanged permanent default; verify old boot and temporary kiosk runtime next.
- Required before durable F promotion: capability/driver-based host decoder
  resolution and matching media-controller passthrough at service generation,
  rather than saved video numbers. Do not broadly pass arbitrary video devices:
  distinguish HDMI capture/RGA/encoders, preserve explicit user selections and
  ordinary containers. Test permuted enumeration, absent decoder, and reboot.
  No main/Actions change or push performed.

### Return verified

- ROCK is back on 999.202609191955-wayland-20260923, confirmed cmdline.
- Old boot skipped container generation because configured touch devices are
  absent. Restored only transient /run Quadlet, network Quadlet via existing
  native generator and default disabled Sunshine policy; omitted two absent
  USB mappings as before this test. Kiosk service active, Weston/session alive.
- Candidate config cmp equals saved original. Current old config has identical
  normalized ConfigTree content to original (one nonsemantic line differs).
- Future boots still need connected configured USB inputs or a deliberate
  optional-device implementation. This temporary /run recovery is not a durable
  fix and does not silently delete user settings.

## Touch reconnected (2026-09-27 ~09:12 CEST)

- User permits touch/display tests. Old default still running. ILITEK now
  enumerates through stable by-id links to event2 (touch) / event3 (mouse).
- Restored these selected mappings to transient runtime Quadlet, resolving
  destinations from by-id; saved user configuration unchanged. Restarted kiosk.
- Weston recognizes touchscreen and mouse and associates both with HDMI-A-1.
  Monitor EDID now identifies RTK FHD HDR and preferred/current1920x1080@60,
  replacing earlier EDID-failure fallback1024x768. Nonconforming EDID warnings
  remain. Rotation transform=rotate-270 implements configured90degrees.
- Chromium, Weston and input reconciliation service active. Asked user to
  confirm actual touch position and swiping; physical outcome pending.
  This is old-image verification, not yet a new-candidate touch test.

## New-image touch boot (~09:20 CEST)

- User confirmed old-image tapping/swiping and orientation correct, then
  protected one-shot booted candidate again with original complete config.
  Independent12min return timer armed, old permanent default unchanged.
- Native startup succeeded with selected USB present. ILITEK touch changed
  event2 -> event1, mouse event3 -> event0. CLI generation resolved stable
  by-id links to correct new destinations without changing saved selections.
- Weston associates both with HDMI-A-1;1920x1080@60 preferred/current and
  rotate-270. Chromium and kiosk active; no failed systemd units; read-only
  input reconciler reports change_required=false. One-shot variable cleared.
- Asked user for actual new-image touch response; confirmation pending.
- User confirms touch works on the new candidate. Physical touch/rotation
  acceptance now complete for this boot with connected ILITEK monitor.
- Kept candidate running for user testing after native service/SSH checks;
  stopped/removed return timer and removed one-shot GRUB hook/variable.
  Verified permanent default remains uuid5-9061c446-3e56-58c8-af43-bffd3ea145ca
  (old image). No unexpected timed reboot remains.
- Separate open issues unchanged: stable decoder-device resolution and startup
  with absent selected USB devices. Touch confirmation does not validate codec
  passthrough under this boot's device numbers or USB unplug/replug recovery.
