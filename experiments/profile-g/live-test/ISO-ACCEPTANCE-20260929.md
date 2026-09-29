# A–D/F/G ISO installation and regression findings — 2026-09-29

Test source: `643733b76cfd382290647ab13cb7723dbb042e8c`.
Runtime workflow: https://github.com/frogro/vyos-arm64-board-builder/actions/runs/36574869550
Full SD/ISO workflow: https://github.com/frogro/vyos-arm64-board-builder/actions/runs/36574869440
Installed image: `999.202609250800-adfg-20260929`, standard `6.18.50-vyos` kernel.
Previous A–D/F image retained as fallback. Main was not modified.

## Verified on the installed system

- Downloaded image checksums, ISO internal checksums, source provenance, embedded
  F/G runtime archives and native CLI modules matched the build artifacts.
- Native `add system image`, unique image name, default selection and real reboot
  succeeded. AP, LAN SSH, Tailscale identity and initial saved configuration survived.
- Critical state contents (333 selected files) survived unchanged. This did **not**
  prove metadata preservation; the ownership failure below was found afterwards.
- Decoder conformance repeated after reboot: H.264 360 frames, HEVC RPS 44 frames,
  HEVC LTR 500 frames, each in software and hardware (1,808 decoded frames total).
- Kiosk switched through native CLI to the new F runtime and was restored after G.
- G startup selected the connected HDMI-A-1 and `plughw:0,0` automatically after
  ALSA card numbering changed. AirPlay recognized an existing registered client;
  no new iPhone streaming acceptance was performed in this round.
- Four 12-second H.264 GStreamer hardware playback runs completed on HDMI/Wayland.
  The user confirmed fluid movement and simultaneous flashes/beeps on ROCK.
- With the permissions-only runtime correction below, native CLI Steam Link
  startup succeeded as UID 1000, with hardware/HEVC requested and the private
  V4L2 Request path selected. The Steam process stayed running and connected to
  Valve's Remote Client service. **This is not a new Legion stream acceptance.**
- Kiosk → Steam Link → Kiosk transition completed; no new HDMI I²C/codec errors
  during this transition or the confirmed AV test. No failed systemd units remained.

## Corrections required by the tests

### Steam archive permissions

Valve's pinned archive contained UID/GID 4009 and private 0700 directories and
executables. Root-only runtime validation passed but the real kiosk user could
not read `/opt/steamlink/bin/shell`. Extraction now discards archive ownership,
sets immutable package files root-owned and grants read/traverse/execute access.
Binary hashes and private decoder manifests remain checked. CI additionally runs
`steamlink.check_runtime()` as `kiosk`.

A permissions-only derived runtime was tested live. The original downloaded ISO
and its embedded runtime do not retroactively contain this correction.

### ISO configuration migration metadata

Upstream `copytree` preserved contents and modes but not directory owners/groups;
its file callback also did not preserve groups. Private PulseAudio and Steam
state became root-owned, preventing receiver startup.

Live state ownership, groups and modes were restored from the previous image,
without changing state contents. The installed updater was backed up and patched.
A disposable copy test against its actual generated helper passed on ROCK.

The common rootfs installer patch now restores UID, GID and modes after copying,
including directories and symlink ownership, without following symlink targets.
It rejects changed upstream anchors and type mismatches. Tests cover 0700/0600
private state, setgid, different UID/GID, symlinks, unchanged contents, and patch
idempotence alongside the existing DTB patch.

Both SD/eMMC images and ISO include the same patched rootfs. Full artifact checks
compare SD and ISO squashfs bytes and require the generated metadata helper and
its call to exist. Fresh SD/eMMC installations therefore carry the corrected
updater; their existing installation/partition layout is unchanged.

**Upgrade boundary:** configuration copying is executed by the *currently running*
installer. When upgrading from an older unpatched image, patch that installer
before `add system image`; merely placing the correction inside the destination
ISO cannot repair the source installer's copy operation. The test ROCK already
has this source-side correction. Reboot/update acceptance of the next rebuilt
artifact is still required.

## Limits / outstanding checks

- Last HDMI `dwhdmiqp ... i2c read error` and unknown ELD at 16:40:17 preceded
  monitor reconnection at 16:40:50. Clean later playback does not prove that
  monitor power-off/hotplug and shutdown transitions are fixed. Do not suppress
  the warnings or claim a driver fix without a reproducer.
- Touch USB enumeration returned. Correct event-node grants were adjusted for
  the G test; a user interaction test after the update remains outstanding.
- Full Miracast, AirPlay, Moonlight, Steam Link streams, D input and F Sunshine
  paths have not all been repeated on this installed image. Earlier protocol
  approvals are not automatically new-image acceptance.
- Neither an eMMC reflash nor another reboot after the live fixes was performed
  in this round. The prior image and secret state backup remain available.
- Backups, pairing keys, raw state and recordings are local only, not committed.
