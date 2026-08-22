# Optional KVM-over-IP preparation

The KVM-over-IP build profile is opt-in. It prepares generic Linux support
for V4L2 capture (including USB UVC), USB capture audio and Linux ConfigFS
gadget operation. These generic kernel capabilities are requested only when
`KVM_OVER_IP=yes`; non-KVM profiles do not receive this KVM gadget delta.

When selected, v4l-utils and GStreamer are installed from the VyOS image's own
APT sources. µStreamer is reproducibly built in a Debian Bookworm ARM64
environment and installed in the image, but it is not started automatically.

The generic Profile-D gadget foundation includes HID for keyboard/mouse,
SourceSink/Loopback for UDC bring-up diagnostics, gadget DebugFS support and
Mass Storage capability for later Virtual Media support. Enabling these kernel
capabilities does not automatically create, bind or expose a USB gadget or
virtual disk. Runtime gadget composition remains a userspace responsibility.

Hardware-specific changes are resolved from
`profiles/kvm-hardware-providers.conf`. Exact board identifiers take priority;
the wildcard provider adds no SoC-specific kernel settings. `rock-5b` selects
`rk3588-synopsys-hdmirx`, which enables the internal Synopsys HDMI receiver
and applies the board-specific USB gadget routing required for the tested
ROCK 5B path. These settings are not applied to Raspberry Pi 5 or to builds
without KVM.

Other RK3588 boards are not selected merely because they use the same SoC.
An exact registry row is added only after the physical HDMI-RX/HPD wiring,
Device Tree and gadget/OTG path have been verified for that board. Until then,
such a board receives the generic V4L2/UVC path and can use a supported USB or
PCIe capture device.

It does not expose a capture device, create a keyboard/mouse gadget, attach
Virtual Media, change the VyOS firewall or enable a listening service. Runtime
state belongs under `/config/kvm-over-ip` so it can survive a normal VyOS
system-image update.

Run `sudo vyos-arm64-kvm-readiness` after connecting the hardware. A detected
`/dev/video*` device establishes capture readiness. Keyboard, mouse and Virtual
Media additionally require a USB port wired to a device/OTG-capable USB device
controller; this cannot be guaranteed generically for every SBC.

The build pins µStreamer `v6.56` to its exact upstream commit and validates
that its required glibc symbol level does not exceed VyOS' glibc 2.36. Release
artifacts include checksums, the GPL license and a source archive generated
from that exact commit.

Stock VyOS does not provide `libjpeg.so.62`, so libjpeg-turbo is linked
statically into the µStreamer executables. The exact Debian package version
and its license are recorded with the build artifacts. Other runtime libraries
continue to come from the VyOS userspace.

Do not install Debian Trixie's `ustreamer` package into the current VyOS
userspace. It upgrades glibc and replaces libevent packages used by core VyOS
components.
