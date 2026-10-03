# Pi 5 / E52C profile integration test branch

Branch: `test/pi5-e52c-profile-support-20261003`, based on main `1c936b1`.
Main and existing releases are unchanged. These are build candidates, not physical hardware test results.

## Ownership and selectable profiles

* A contains board-specific kernel configuration, Device Tree and onboard firmware.
* B adds optional network hardware (including external Wi-Fi/Bluetooth adapters).
* C adds Tailscale; D adds capture and supported gadget control.
* Pi 5 F and G have a separate Debian/Mesa VC4/V3D runtime, without Rockchip binaries or Mali firmware. Each application remains independently selectable.
* E52C supports A–D. D accepts USB video capture. The sole USB-A OTG port cannot simultaneously be a USB host for the grabber and a USB peripheral for native HID. No gadget provider is installed for E52C.

## Pi 5 hardware

The A kernel enables RP1 CFE, PiSP BE, VC4/V3D and the Raspberry Pi HEVC decoder as modules. BCM2712 IOMMU and GPU power support are built in. The pinned downstream HEVC source requires a narrow media-request completion backport and four column-format identifiers. Sources and hashes are in `profiles/base-hardware/kernel-patches/raspberry-pi-5/provenance.json`.

The DT describes GPU, HEVC, PiSP and both RP1 CSI receivers. CSI nodes remain disabled pending a sensor-specific endpoint/clock/I2C configuration. A TC358743 or camera is not automatically detected or configured by enabling its module. Sensor overlays and physical capture remain a separate validation step.

DWC2 supports dual role in A; its USB-C device node remains disabled in A/B/C. Selecting D applies the peripheral overlay to the versioned DTB; RP1 USB-A controllers remain hosts. A suitable USB-C power/data arrangement is required. Actual UDC enumeration and HID/mass-storage need a Pi hardware test.

Onboard Bluetooth uses pinned Raspberry Pi BCM4345C0/C5 firmware with its licence. DT serdev/hci_bcm owns initialization; no competing hciattach service is added. Firmware download checksums are verified before installing any files.

Pi 5 has no hardware H.264 encoder. Sunshine uses software encoding. The HEVC kernel compilation result does not establish FFmpeg, GStreamer or Steam Link hardware-decoding compatibility: the downstream column-buffer layout needs a matching userspace path. Auto software fallback remains available. No hardware-decoding success is claimed without a stream test.

## E52C hardware

A explicitly requires onboard Realtek Ethernet, Rockchip PCIe/PHY, MMC/eMMC, thermal/ADC/OTP, RTC, LED and button support. Router-critical components are built in; optional controls are modules. USB dual-role capability is available in the kernel, but the host DT is preserved for USB capture. F/G are not selected on this headless board.

## Updates and fallback

No configuration schema or storage-layout migration is introduced. Pi DT/kernel/initramfs and its D0 overlay remain versioned together through the existing native firmware update provider. Switching back selects the old complete boot payload. E52C retains the U-Boot/extlinux update provider. Test builds must retain previous images until boot, networking and selected profiles have been exercised on hardware.

Local validation includes compiled DT overlay application, actual Linux 6.18.54 Kconfig resolution, firmware checksum failure atomicity, profile isolation and boot/update/fallback tests. Full image construction and hardware validation are separate checks.
