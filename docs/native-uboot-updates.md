# Native U-Boot/extlinux candidate updates

This candidate continues `e52c-vendor-uboot-test` and includes the shared
integration through `4419502`. Its reference is the E52C network image from
builder commit `6513987`, using current hardware metadata and vendor U-Boot.
It preserves that boot path; it does not introduce EDK2 or replace SPI firmware.

## First installation and migration

Use the new `.img.xz` for the first installation of this candidate. The old
hardware-proven E52C image has neither these lifecycle hooks nor an installed
boot identity in its extlinux command line. Installing the new ISO with the
old image's installer is **not** a supported migration method. Preserve the
old card/image and configuration as the recovery reference.

The new boot menu explicitly supplies `BOOT_IMAGE=/boot/<name>/vmlinuz`, so
VyOS recognizes an installed system and the correct running image name.
The serial defaults are `ttyS2`, 1500000 baud. The existing speed CLI constraint
is extended to allow 1500000, including the reference cache and legacy template;
all original speed values and unrelated reference nodes remain intact.

## Lifecycle contract

On this provider, standard `add system image`, `set system image default-boot`
and `delete system image` operations synchronize the native boot menu with
VyOS's per-version GRUB metadata. The GRUB files remain the image database;
the board itself boots through vendor U-Boot and extlinux.

The initial image and each accepted update contain matching board, architecture,
feature-profile, firmware-provider, update-provider and DTB metadata. Updates
that do not match the native contract are rejected. The new ISO carries the
same `live/boot-provider.json` used to initialize its root filesystem.

The FAT partition is resolved on the **same disk as the mounted persistence
partition**, by the provider's partition number and filesystem, and verified
against its provider marker. A global `EFI` label is not used to select a disk.
Kernel/initrd/DTB sets are content-addressed, so updates never overwrite the
payload of an existing boot entry. Identical payloads share storage, but each
image has its own union-root path and boot identity. Both extlinux locations
are updated only after all files have been written. Software-level publication
failures restore menu copies and the preceding GRUB state. Deleted payloads
are pruned after both menus reference the remaining versions.

A small FAT boot partition limits the number of distinct kernel/initrd sets.
Insufficient space fails the operation without switching the boot menu; remove
an unused image before retrying. This does not provide a hardware power-failure
transaction across FAT and ext4: abrupt power removal still requires recovery
media. Runtime failures are reported rather than silently leaving GRUB and
extlinux pointing to different defaults.

Renaming an already installed image is explicitly rejected on this provider,
because upstream renames through temporarily inconsistent state. Add the ISO
under the intended name instead. This restriction does not affect ROCK/EDK2,
Pi native firmware or ordinary UEFI installations.

## Hardware acceptance (not yet established for this candidate)

1. Flash the new `.img.xz` on a separate test card. Confirm boot, serial login
   at 1500000 baud, SSH, both ports, `show version` and `show system image`.
   `show version` should no longer classify this native installation as livecd.
2. Run `sudo vyos-board-diagnostics` and preserve its output. The build also
   publishes `interrupt-dtb-audit.json`, which rejects RK358x GIC/ITS nodes
   lacking `dma-noncoherent` or containing contradictory `dma-coherent`.
3. Run `add system image /config/<candidate>.iso` and choose a distinct image
   name. Check the selected default, reboot and confirm the exact running name,
   serial login and both network interfaces.
4. Select the previous image with `set system image default-boot <old-name>`,
   reboot and verify rollback. Select the new image again and verify it.
5. Delete only a non-running, non-default test image. Verify both image listing
   and extlinux entries, then reboot once more. Repeat cold boot separately.
6. Map physical LAN/WAN labels by plugging only one cable at a time. Record
   PCIe address, interface and negotiated link speed. Do not swap interface
   names based on an unconfirmed label observation.
7. Once ITS/MSI errors are understood, test 2.5-Gbit link negotiation and iperf
   throughput against a known 2.5-Gbit peer. Link speed and routed/NAT throughput
   are separate measurements. The saved archive does not contain a verifiable
   500-Mbit throughput result.

The available saved forum HTML contains the full successful-image output and
Frank's follow-up, but later Bobby posts only as lazy-loaded placeholders.
The supplied prior-chat summary reports coldboot/reboot success and ITS errors;
their complete original logs remain needed for diagnosis. The gate and support
bundle make the next test evidence explicit; they do not claim to have fixed a
hardware ITS fault without testing it.
