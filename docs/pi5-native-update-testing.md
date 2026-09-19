# Pi 5 native image update experiment

Status: implemented for testing; physical Pi 5 validation pending. No public
update feed is enabled. The board repository still publishes installation
images only. Central builder artifacts include the experimental ISO.

## Contract

Install the new raw image on a separate SD card first. Old Pi installations
lack the lifecycle hooks and cannot acquire them by safely selecting the new
ISO using their old installer. Keep the original boot medium unchanged.

The existing VyOS image manager remains authoritative. Its image add/delete,
default selection and console changes invoke a provider adapter. The adapter
resolves FAT partition 1 on the actual persistence disk and verifies its board
marker. It stages the selected version's kernel, initramfs, firmware-ready DTB,
D0 overlay and derived command line in a content-addressed directory. It flushes
that directory before replacing config.txt with an os_prefix pointing to it.
The command line includes BOOT_IMAGE and the matching vyos-union path.

A missing or incompatible image, insufficient FAT space or a detected write
failure aborts the operation and restores boot-selection metadata. The Pi
adapter retains old bundles and config.previous.txt for manual recovery. It
does not update EEPROM or the pinned firmware blobs, and does not provide an
automatic watchdog rollback or a GRUB menu on the Pi. FAT power-loss corruption
cannot be excluded. Repeated tests can fill the 512 MiB FAT partition because
bundle garbage collection is deliberately deferred.

## Hardware test sequence

1. Boot the new raw image on a spare medium. Check serial/display console,
   Ethernet, WLAN, time, `show version` and `show system image`.
2. Use native `add system image <matching Pi ISO URL>` with a distinct image
   name. Retain the old version and copy the configuration when prompted.
3. Check `show system image` and the next-boot selection. Reboot and verify
   the running version, networking and `/proc/cmdline` (BOOT_IMAGE and
   vyos-union must both reference the selected version).
4. Use `set system image default-boot <previous-image-name>` in operational
   mode, reboot, and verify the previous version. Then select the new image
   again. Test deletion of an unused image, never the only recovery image.
5. Test a cold boot and repeat with a second genuinely different kernel/ISO.
   Reinstalling the same ISO under another name tests selection but not kernel
   compatibility across upgrades.

If the selected image does not boot, use the retained original medium. Offline
recovery can restore RPICFG/config.txt from vyos-boot/config.previous.txt while
retaining its referenced payload. This is a manual recovery option, not an
automatic firmware fallback.

## Source rollback

The pre-change source is preserved in
`backup/pi5-before-native-updates-20260919` at `d1258ed`.
Revert the dedicated Pi lifecycle commit to remove this experiment from future
builds without rewriting development history. Reverting code does not migrate
an already-installed medium back; use the retained raw image/boot medium.

Build 35456147338 reached final assembly but failed the generic raw-DTB byte
comparison: the Pi finalizer now deliberately stores the firmware-ready DTB
(with the Wi-Fi MAC handoff overlay) in the installed version for ISO updates.
The release gate now reconstructs that expected DTB from the original kernel
artifact and provider overlay before comparing bytes. Other providers retain
raw-artifact comparison. The real provider fixture tests valid transformed DTB
acceptance and corrupted-DTB rejection; the seven Pi lifecycle tests also pass.
This fixes build validation, not outstanding physical Pi update acceptance.
