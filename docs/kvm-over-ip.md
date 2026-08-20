# Optional KVM-over-IP preparation

The KVM-over-IP build profile is opt-in. It prepares generic Linux support
for USB UVC video capture and USB HID gadget operation. When selected,
µStreamer is reproducibly built in a Debian Bookworm ARM64 environment and
installed in the image, but it is not started automatically.

It does not expose a capture device, create a keyboard/mouse gadget, change
the VyOS firewall or enable a listening service. Runtime state belongs under
`/config/kvm-over-ip` so it can survive a normal VyOS system-image update.

Run `sudo vyos-arm64-kvm-readiness` after connecting the hardware. A detected
`/dev/video*` device establishes capture readiness. Keyboard and mouse
emulation additionally require a USB port wired to a device/OTG-capable USB
device controller; this cannot be guaranteed generically for every SBC.

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
