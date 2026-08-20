# Optional KVM-over-IP preparation

The KVM-over-IP build profile is opt-in. It prepares generic Linux support
for USB UVC video capture and USB HID gadget operation without installing or
starting a streaming application.

It does not expose a capture device, create a keyboard/mouse gadget, change
the VyOS firewall or enable a listening service. Runtime state belongs under
`/config/kvm-over-ip` so it can survive a normal VyOS system-image update.

Run `sudo vyos-arm64-kvm-readiness` after connecting the hardware. A detected
`/dev/video*` device establishes capture readiness. Keyboard and mouse
emulation additionally require a USB port wired to a device/OTG-capable USB
device controller; this cannot be guaranteed generically for every SBC.

Do not install Debian Trixie's `ustreamer` package into the current VyOS
userspace. It upgrades glibc and replaces libevent packages used by core VyOS
components. A compatible, reproducibly built ustreamer payload will be added
separately after its build and runtime dependencies are validated.
