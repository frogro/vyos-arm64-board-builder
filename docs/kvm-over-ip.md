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

Profile D installs the reusable gadget runtime, `vyos-kvm-gadget`. Native
VyOS configuration is integrated under `service kvm-over-ip`; the conf-mode
handler translates committed VyOS configuration into the video/streaming
runtime and calls the gadget manager for HID, USB routing and Virtual Media.
The lower-level gadget interface remains available for diagnostics:

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

The native VyOS configuration hierarchy is:

    service kvm-over-ip
      video
        backend ustreamer|gstreamer|ffmpeg
        device /dev/videoN
        resolution WIDTHxHEIGHT
        framerate FPS
        bitrate KBIT/S
        gop FRAMES
        listen-address IPv4
        port PORT
      keyboard
      mouse
        absolute
        relative
      usb
        port <provider-defined semantic port>
      virtual-media
        file /config/kvm-over-ip/media/FILE.iso

Board-specific implementation details remain internal. On the validated ROCK 5B
path, `ffmpeg` uses `ffmpeg-rockchip` with `h264_rkmpp`, while `gstreamer` uses
the Rockchip MPP encoder. Generic boards keep the generic software/backend path.
µStreamer JPEG quality is fixed internally at 80 and is intentionally not
exposed as a VyOS CLI setting.

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

For the ROCK 5B HDMI-RX provider, the video runner synchronizes the currently
detected HDMI DV timings before opening the capture device. This prevents a
detected 1080p60 input from remaining on a stale 640x480 capture timing.

Other RK3588 boards are not selected merely because they use the same SoC.
An exact registry row is added only after the physical HDMI-RX/HPD wiring,
Device Tree and gadget/OTG path have been verified for that board. Until then,
such a board receives the generic V4L2/UVC path and can use a supported USB or
PCIe capture device.

Building a KVM-enabled image alone does not expose a gadget, Virtual Media or
a network stream. Runtime activation follows committed `service kvm-over-ip`
configuration. With no KVM service configuration present, the image remains
prepared but inactive. Runtime state and media belong under
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

## HDMI signal recovery and HID activation (2026-09-14)

The `rk3588-synopsys-hdmirx` provider runs capture under a signal supervisor.
It waits without repeatedly launching encoders when HDMI source power/link is
absent. Signal loss or a DV-timing change stops the capture process group;
returning input starts the existing runner, which synchronizes detected timings
before opening capture. Small measured pixel-clock jitter is tolerated.
FFmpeg/GStreamer wait for the local RTSP listener and additionally undergo a
bounded packet-flow check (15-second startup grace, then every 10 seconds).
Two unsuccessful packet checks restart even a process that is still alive.
An unresponsive encoder receives SIGKILL after five seconds of SIGTERM grace.
Generic V4L2 providers retain their existing runner behavior. USB HID is not
reconfigured by video recovery. Browser reconnection is a separate client concern.

The gadget helper also returns success after initially adding keyboard, mouse
or virtual media to an unbound gadget. Previously its final conditional rebind
returned status 1 when no binding existed; native CLI activation consequently
failed before the final bind step.

On ROCK 5B image `999.202609141528`, the helper correction allowed native CLI
commit/save of keyboard and both mouse modes. The host enumerated all three;
typed text and both mouse motion modes were confirmed by the tester. HDMI
unplug/replug was recognized by the supervisor at 22:05:49/22:06:02 CEST, with
automatic encoder restart. A later refinement tolerates pixel-clock jitter;
the updated runtime was checked with 121 H.264 packets in two seconds at
1920x1080/60 and HID remained configured. Full ROCK reboot persistence and a
repeat target-computer reboot remain acceptance steps. GStreamer and ustreamer
recovery are not hardware-validated by this FFmpeg test.

These fixes were installed in the running test image with backups of the old
helpers. The published `999.202609141528` ISO does not contain these changes;
future images must be built from the corrected source to carry them forward.
