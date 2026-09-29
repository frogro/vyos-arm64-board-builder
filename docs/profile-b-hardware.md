# Profile B hardware coverage and rollback

B adds transport/peripheral support; it does not activate a Bluetooth daemon,
create a USB gadget, change networking, or claim physical validation.
`m` modules can autoload when matching hardware is present.

## Sources and verification

Use the selected Linux Kconfig/source, actual DT and compiled `.config`.
Manufacturer specifications are a versioned inventory, not a live build input.
The builder still uses its existing pinned hardware-reference machinery; this
change does not replace that pipeline or require downloading specifications.

Shared Bluetooth transports and their boolean protocol selectors are in
`profiles/b-hardware/bluetooth.config`; existing built-in selections are preserved.
USB covers Intel, Realtek, MediaTek, Broadcom and Qualcomm combo functions.
UART covers Broadcom/Realtek/Qualcomm; SDIO covers generic and Marvell devices.
`profiles/wifi-bluetooth-map.tsv` accounts for every optional WLAN catalog entry.
There is no one-Bluetooth-driver-per-WLAN-driver relationship.
Firmware supplements are module-scoped and cover runtime-generated BT filenames
not fully declared by MODULE_FIRMWARE in Linux 6.18.

Optional generic B requests add I2C/spidev, gadget function modules and IR.
Unavailable/unsatisfied optional requests are reported as skipped. The resolver
rejects changes that weaken any existing built-in/module capability.

## Orange Pi 5 Plus

Exact-board requirements correct the DT OTG versus host-only kernel mismatch:
DWC3 dual-role, USB role switching, FUSB302/TCPM, USB-DP PHY, DP output/altmode,
and ES8388/ES8328 analog audio. No other board receives that mode override.
Readiness checks run against the actual Kbuild `.config` after olddefconfig.
EDK2 v1.1 is promoted from the already boot-tested Orange Pi test branch to main,
matching the installed image; this changes the Orange Pi default provider only.
Existing U-Boot installations must NOT install this EDK2 update ISO.
Pi/ROCK/E52C provider entries, partition/update code remain unchanged.

GPU/VPU/NPU, concrete CSI sensor overlays and receiver applications remain separate.
Profile D already requests VIDEO_TC358743 and validates its availability; that
alone does not configure a camera/CSI capture pipeline on a new board.

## Fallback

Pre-change main: 7d1af73, tag fallback-before-profile-b-hardware-20260929.
Revert subsequent hardware commits in reverse order rather than resetting history.
Keep the currently working Orange Pi EDK2 image; do not delete it during update.
A Git rollback is not a device rollback. New images require boot, USB-C, analog
audio, BT and network regression tests. No new on-device kernel was installed.
Build only A+B, assert update provider efi-firmware-dtb, and do not publish the
candidate as Latest until validation. SD/eMMC raw images and update ISO use the
same kernel/module payload.

## Target coverage

The user's target is an Orange Pi A/B image with all supported board drivers
and firmware already available, so later profiles activate applications and
hardware configuration without rebuilding the kernel. This first increment
covers USB-C, Bluetooth and analog audio plus common optional peripherals.
GPU/VPU/NPU and camera-specific pipelines remain explicit coverage gaps, not
claims of complete hardware readiness. Unsupported hardware needs source/DT
work; a Kconfig request alone does not establish functioning support.
