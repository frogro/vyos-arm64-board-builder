# A-D foundation plus existing F: update preparation, 2026-09-26

User decision: new A-D as foundation; add the existing F implementation for the
next ROCK test. E remains excluded. Native update ISO, no SD reflash. This note
prepares the work; it does not claim an A-D/F image has been assembled or installed.

## Pinned inputs and live ownership

- A-D candidate: branch integration/d-media-20260926, commit63767ef,
  Actions run36267716867. Still building at preparation time; record successful
  final artifacts/provenance/hashes before reuse.
- Existing F source: feature/kiosk-profile-f, including d640ae5 (same-user
  Weston/Chromium plus separate seatd),3e387e4 and48e3a23.
- Working runtime: localhost/vyarm-kiosk:wayland-user-20260926,
  image3b7a84a541ae1b766062167ef3a598b20609a345df3a7b8c5fef0b73fa800fb8.
- Live container uses /config/kiosk/state -> /state,132MiB at inspection;
  current config.boot about8KiB. Do not include either in a published image.
- Native persistent Podman graphroot:
  /usr/lib/live/mount/persistence/container/storage.
- Live kernel6.18.50-vyos. Equal release strings alone do not prove module ABI
  equivalence: the F live kernel has additional patches and signatures.
- Old installed system image and old container tag must remain as rollback.

## Assembly sequence (on NUC, isolated build directory)

1. Audit successful A-D artifacts: board/firmware contract, raw source pin,
   vyos-1x version, kernel source/config/patches, modules/DTB, image profile and
   update compatibility. Keep A-D artifacts immutable. Create a distinct A-D/F
   version/output directory and record every input hash.
2. Start from A-D source/provenance, selectively add F source changes. Do not
   replace the entire tree with the old F checkout: retain latest image-name
   fix, D metadata CLI and media patches. E and experimental abandoned reset
   candidates remain out. Deduplicate the shared RGA corrections; prefer the
   new consolidated D patch, retaining its disabled legacy behavior.
3. Audit kernel/config delta needed by F: GPU/display/touch/audio, validated
   V4L2 H264/HEVC/VP9/AV1 patches and device-tree/IOMMU dependencies. If the A-D
   kernel lacks these (expected), build the matching F-capable kernel, full
   modules, DTB and required OOT modules from the new base. Do not copy old
   .ko files by matching uname alone. Regenerate matching initramfs. Preserve
   established bootchain. Chromium reuse is conditional on decoder/UAPI tests;
   a new Chromium compilation is not automatically needed for this assembly.
4. Build the complete matching vyos-1x package with both new D colorimetry and
   current F container/kiosk/Sunshine nodes and handlers. Regenerate complete
   template/reference caches using that version's native generators. Do not
   install the old Sep23 package over the new A-D CLI: it could lose D updates.
5. Export/reuse the verified immutable working F runtime, or rebuild under a
   new unique tag if any content changes. Embed archive + image ID + SHA256 in
   runtime.json through stage-runtime.py. Never overwrite the old tag with new
   contents. Include same-user Wayland fix, crashpad handler and /usr/bin/weston
   DRM backend (not the separate headless-only Weston). Keep X11 available.
6. Include F host integration: persistent runtime import before config load,
   scoped generators/startup and touch recovery, current helper/policy files.
   Initial setup must never run automatically during update. Do not reset URL,
   rotation, decoding flags, granted devices or remote/audio preferences.
7. Assemble distinct rootfs/kernel/initramfs/DTB and create the native update ISO
   with correct A-D/F profile identity and hashes. No host disk is a build target.
   Previous repack-wayland.sh is historical, not an executable template for this
   job: it hardcodes old versions/paths and includes destructive temporary cleanup.

## Pre-install gates

- Offline ISO checksums, board/update-provider compatibility, unique image name.
- Verify complete D+F CLI owners/caches and dependencies in rootfs.
- Verify runtime archive metadata matches its actual image ID; current saved
  kiosk tag must be available after boot. Importer must not retag collisions.
- Verify preserved sample config (including current F fields and new D field)
  validates against the new native CLI, without committing it to repository.
- Matching kernel/modules/signatures and required boot/display/decoder DT nodes.
- Sufficient boot/persistence space for both images, runtime and rollback backup.
- F offline preservation/import tests passed5/5 during this preparation;
  these do not substitute for actual upgrade/boot acceptance.

## Installation (later, not performed tonight)

1. Secure dated backup of config directory, SSH host keys and kiosk state. Keep
   credentials/private state out of Git. Briefly stop kiosk for a consistent
   browser/Sunshine state backup and installer copy; restore service on failure.
   Retain local/persistent and independent off-device backups where possible.
2. Run native `add system image <new-A-D-F.iso>`; accept configuration directory
   and SSH host key copying. Do not format persistence, run first-install setup,
   prune containers, delete old system images, or reset pairing.
3. Verify new boot entry and copied configuration before planned reboot. Retain
   boot-menu selection of the old image and a tested independent recovery path.
4. After reboot verify kernel/build identity, import service, saved config,
   runtime tag, Wayland90, touch/reconnect, four decoder short tests and D checks.
   Compare settings and persistent data against the backup. Switch runtime tag
   explicitly only if assembly changed it; no blanket defaults overwrite.
5. If regression occurs, select the previous system image; restore the saved
   runtime tag/config/state as needed. Persistent container data can be shared,
   so boot rollback alone is not a rollback of modified browser/pairing data.

No SD reflash is required to retain settings. A destructive fresh install is a
separate later first-install test on a spare card, not this update procedure.
