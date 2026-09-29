# Isolated test3 deployment preparation — 2026-09-21

Target version: `6.18.50-vyos-f-test3`.
Local source/build/staging directory:
`/mnt/entwicklung/projekte/VyOS/arm/vyos-arm64-board-builder/tmp/kiosk-decoder-20260921`.
Remote staging directory: `/config/kiosk-test/kernel-test3`.

Full Image/modules/ROCK5B DTB build succeeded. Modules installed into local
`stage` with `INSTALL_MOD_STRIP=1`; the kernel build's normal modules_install
signing/compression steps are retained. Package contains only the new version,
not build/source symlinks or signing keys. SHA256 verified after transfer.
Modules installed alongside old versions under `/lib/modules` on the ROCK;
this does not load them into the running test2 kernel.

The initramfs configuration is a private copy of `/etc/initramfs-tools`, with an
extra hook copying all of this version's modules. Existing Panthor firmware hook
is retained. A separate `/boot/config-6.18.50-vyos-f-test3` is provided to
mkinitramfs. Build runs in `vyarm-test3-initramfs.service` with 1 GiB limit.
No normal initrd, kernel, DTB or global initramfs configuration is replaced.
Before use, inspect the service result, initramfs contents and artifact hashes.

## Recovery constraint

Existing bootloader defaults select the original VyOS image, **not the currently
running one-shot test2 kernel**. Saved baseline is `grub.cfg.d.before` and
`grubenv.before` in the staging directory. Keep existing defaults untouched.
A separate test3 one-shot hook must consume/clear its next_entry, like test2.

The live Synopsys DesignWare watchdog is inactive. Its kernel driver calls
`watchdog_stop_on_reboot`; simply enabling a userspace watchdog now does not
establish protection across an early boot hang. A normal userspace timer also
cannot recover a kernel which never reaches userspace.

Do not select/reboot test3 until physical recovery availability or a verified
independent automatic recovery mechanism is established. User has been asked
whether they can power cycle the ROCK if needed; answer is pending. No test
reboot is implied by artifact preparation.

After boot: verify uname, both production services, kernel log and media graph;
identify actual video/media decoder pairs. Run explicit GStreamer stateless
H.264/HEVC comparison fixtures (three process starts each) in the isolated image.
No module unload/unbind experiment; previously reviewed PM/remove concerns remain.
Chromium hardware decode is a later gate, not inferred from a GStreamer pass.

Preparation completed at 12:29 UTC: initramfs service exit0, 42MiB; decoder,
Panthor/firmware, network and root filesystem modules verified in archive.
Version-specific boot artifacts and separate test3 menu/one-shot hook installed;
both GRUB fragments pass syntax checking. next_entry is empty: test3 has **not**
been selected or booted. Normal boot files/default remain unchanged.
