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

Profile D also installs the first runtime layer, `vyos-kvm-gadget`. It is not
started automatically and does not change the VyOS configuration tree. The
initial D3 interface provides:

    vyos-kvm-gadget create
    vyos-kvm-gadget destroy
    vyos-kvm-gadget bind
    vyos-kvm-gadget unbind
    vyos-kvm-gadget rebind
    vyos-kvm-gadget status
    vyos-kvm-gadget keyboard enable
    vyos-kvm-gadget keyboard disable
    vyos-kvm-gadget mouse absolute enable
    vyos-kvm-gadget mouse absolute disable
    vyos-kvm-gadget mouse relative enable
    vyos-kvm-gadget mouse relative disable
    vyos-kvm-gadget virtual-media attach <iso>
    vyos-kvm-gadget virtual-media eject
    vyos-kvm-gadget virtual-media status

The manager owns ConfigFS/libcomposite setup and gadget composition. Board-
specific UDC names remain in provider runtime metadata rather than in the
generic manager. This keeps a later dedicated-port versus USB-C/PD-injector
choice board-specific while preserving one common runtime interface.

Keyboard, absolute mouse and relative mouse are independent HID functions.
The ROCK 5B hardware validation demonstrated all three simultaneously as a
three-interface USB composite gadget. Absolute pointer reports use 16-bit
coordinates, while relative pointer reports carry signed movement deltas.

The first Virtual Media runtime supports ISO files as removable, read-only
CD-ROM media. Media files are restricted to `/config/kvm-over-ip/media` by
default. Eject uses the ConfigFS `forced_eject` control so a host media lock
does not require reconnecting the whole USB gadget. The ROCK 5B validation
demonstrated an attached ISO as `/dev/sr0`, a no-medium state after eject, and
successful re-attach/read while the HID functions remained available.

Writable CD-ROM media is intentionally unsupported. Future Virtual Media
expansion may add separate `disk-read-only` and `disk-read-write` modes for
USB disk images; the writable mode is intended for controlled data transfer
or backup and will require additional mount/sync/eject safety checks.

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

Nothing is exposed automatically at boot: the runtime does not create or bind
a gadget, attach Virtual Media, change the VyOS firewall or enable a listening
service unless explicitly invoked. Runtime state and media belong under
`/config/kvm-over-ip` so they can survive a normal VyOS system-image update.

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
