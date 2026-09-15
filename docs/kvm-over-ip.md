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

The ROCK 5B dedicated gadget port is the lower blue USB-A socket. A connection
to another USB host **requires a VBUS-blocking (power-off) adapter** which
interrupts the 5 V conductor but preserves data and ground. A USB data blocker
is not suitable. The board shares `USB_HOST_PWREN_H` between both USB-A
connector pairs, so the gadget overlay preserves host power and the other
host PHYs. Cutting their shared supply also disables external USB devices.
This is a ROCK 5B wiring requirement, not a change to other board providers.

On 2026-09-14, restoring host power and the host PHY and removing the GPIO-low
hog restored enumeration of a Logitech Unifying receiver (`046d:c52b`), with
keyboard and mouse input devices using the existing `hid-generic` driver.
That test had the gadget cable disconnected; simultaneous physical input
forwarding to the target remains a separate test.

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

## Selected local USB keyboard and mouse forwarding

Use stable `/dev/input/by-id` event paths, not numbered `eventN` devices.
For the tested Logitech Unifying receiver:

```text
configure
set service kvm-over-ip keyboard
set service kvm-over-ip mouse relative
set service kvm-over-ip local-input keyboard /dev/input/by-id/usb-Logitech_USB_Receiver-event-kbd
set service kvm-over-ip local-input mouse /dev/input/by-id/usb-Logitech_USB_Receiver-if01-event-mouse
commit
save
exit
```

The receiver must remain on a host port. Only the selected keyboard and mouse
are grabbed exclusively and forwarded to the target; their normal input no
longer reaches the local console while forwarding is active. System-power and
consumer-control event devices are not selected. No keystrokes are logged.
The target OS determines the keyboard layout. Keyboard LED feedback and
multimedia keys are not implemented.

Configuration follows `get_config`, `verify`, `generate`, `apply`. The config
script creates root-readable runtime JSON under `/run`, starts the service
after gadget setup and stops it before gadget changes or configuration removal.
The service is started by VyOS configuration application, not independently
enabled with systemctl. Missing receivers may be configured: the daemon waits
for them rather than failing boot. Stable paths are reused after hotplug.

Remove forwarding with `delete service kvm-over-ip local-input`, then `commit`
and `save`. Existing video and virtual media configuration is preserved.
The XML, config script and service are included by the KVM image installer.
Saved settings can be carried into a future image containing this extension;
older images without these CLI nodes are not guaranteed to load them. Updating
the current checkout does not change already-published images.

KVM builds now prepare an isolated matching VyOS-1x source checkout, add the
profile XML as `.xml.in` plus config and service sources, and run the upstream
`dpkg-buildpackage` targets. CLI templates, reference caches and configd includes
are generated together by VyOS. The package is installed before board patches;
there is no post-build reference-tree merger. Non-KVM builds skip this step
and keep the base package. Tailscale preparation alone does not modify VyOS-1x.

The actual base package version must identify an accessible clean source commit.
An unresolved/dirty version stops the KVM build rather than selecting another
rolling revision. Artifacts include the source commit, recipe hash, container
image ID and package checksum. Package outputs are isolated and are not reused
from a shared cache. The build container must provide the dependencies for that
source revision. Full package/image validation is required before releasing this
new source-build path.

Hardware tests on 2026-09-15 confirmed physical keyboard input through the
ROCK into the target desktop, BIOS and Alpine live console, mouse operation
on the desktop, and recovery after receiver unplug/replug. Native CLI boot
restoration must be verified separately after installation.

## HDMI-to-CSI preparation (Profile D)

The KVM kernel delta requests `CONFIG_VIDEO_TC358743=m`, I2C and the V4L2
subdevice API. The readiness requirements also check these capabilities in
the resulting kernel configuration. The upstream Toshiba TC358743 driver
supports an HDMI-to-MIPI-CSI-2 bridge; this is not a generic driver for every
HDMI-to-CSI adapter. Non-KVM profiles receive no additional request for it;
a base or board configuration may independently include the driver.

Source: https://github.com/torvalds/linux/blob/v6.18/drivers/media/i2c/Kconfig

Driver inclusion alone does not provide a working capture source. The exact
board/module combination still needs a CSI receiver driver and a matching
Device Tree/overlay with I2C addressing, clocks, GPIOs, CSI lanes and media
endpoints. EDID, media-graph setup and signal detection may need provider
initialization. No overlay or CSI port is automatically enabled by this change.
No HDMI-to-CSI hardware has been validated for this profile yet.

A CSI camera supplies its own picture; an HDMI-to-CSI bridge captures an HDMI
source. The planned shared source-selection layer accommodates both through
providers: discover capture-capable nodes (exclude metadata-only nodes),
report signal status as known or unknown, and choose a backend-compatible
format. USB frame delivery alone must not be treated as proof of HDMI signal.
This architecture is planned; adding the bridge module does not implement
CSI source selection or a libcamera pipeline.

### Geekworm bridge modules

Manufacturer documentation checked on 2026-09-15 identifies the Toshiba
TC358743XBG as the capture bridge in C779, C790, C792, X630, X1300 and X1301.
These modules share the `VIDEO_TC358743` driver requested by Profile D; no
separate vendor-named Geekworm capture driver is needed. This is a chip/driver
mapping, not a claim of tested VyOS support for these products.

C792 additionally uses a GSV2001 for its HDMI split/loop-out path. The vendor's
capture setup still uses TC358743; loop-out behaviour has not been validated
here. Connector, lane count and optional I2S audio differ between modules.
Audio needs its own wiring, sound-card/codec and Device Tree integration;
the video bridge module alone does not enable audio capture.

The Pi 5 instructions explicitly configure an RP1 CFE media graph, load EDID
and synchronize DV timings. A future provider must discover the matching
media entities/subdevices instead of copying fixed `/dev/video0`,
`/dev/v4l-subdev2` or I2C bus numbers from the vendor demo. Raspberry Pi
`tc358743`/`tc358743-audio` overlays are board/boot-path specific and must not
be enabled globally for ROCK or other SBCs.

References:
- https://wiki.geekworm.com/C792 (module comparison and capture setup)
- https://wiki.geekworm.com/C790
- https://wiki.geekworm.com/CSI_Manual_on_Pi_5

### Raspberry Pi implementation checklist (planned, not enabled)

- Identify the Pi model, actual kernel/boot path, CSI connector and bridge
  module before selecting receiver support or overlays.
- Verify the `tc358743` overlay exists in the image. Use four-lane operation
  only where both the module and the selected CSI connector wire four lanes;
  do not apply the vendor's CAM1 example to every Pi connector.
- On Pi 5/CM5, verify RP1 CFE support and discover its media graph. Older Pi
  receiver paths (for example Unicam) require their own matching setup.
- Load a suitable EDID, query and synchronize the bridge DV timings, configure
  media links/pad formats and negotiate the capture format. Discover entity
  and subdevice identities; never assume fixed device numbers.
- Treat optional `tc358743-audio`/I2S setup separately and verify wiring and
  kernel sound support before enabling it.
- Preserve the selected hardware configuration through the image update path.
  Validate capture, signal loss/recovery and reboot on real Pi hardware before
  marking the provider supported. No Pi boot configuration is changed yet.

### Next integration gate

Implement the shared capture/provider selection and backend format negotiation
for the already tested ROCK HDMI and Elgato USB paths first. Test selection
with one/multiple devices, unknown signal status, metadata-node exclusion and
explicit device overrides. Exercise all three backends through the native VyOS
CLI, then build a new KVM-profile image. Reboot and update persistence checks
follow installation of that image; CSI remains prepared but unvalidated.

### Initial shared selection live validation (2026-09-15)

The capture helper and runner were patched temporarily into image
999.202609151132 on ROCK 5B, with originals backed up under
`/config/kvm-over-ip/backups/capture-integration-20260915`. With internal HDMI
unplugged and Elgato HD60 X attached, automatic selection chose its persistent
USB capture node and excluded the metadata sibling. Actual native CLI commits
selected NV12 for FFmpeg/MPP and GStreamer/MPP, and YUYV for uStreamer.
Both H.264 streams decoded at 1920x1080; uStreamer reported online 1080p and
60 capture fps. H.264 bitrate/GOP must be removed when selecting uStreamer,
as enforced by the existing CLI. The original FFmpeg/8000/60 configuration
was restored after testing. No reboot or image update was performed.

The new helper skips HDMI DV-timing queries when the ROCK's power_present
control reports no source, avoiding the driver's expected no-link log noise.
Source signal status for the USB grabber remains explicitly unknown. The last
source is retained in /run across service/backend restarts; this selection
memory is not persistent across boots. Explicit device overrides take priority.

Outstanding: validate the shared selector with internal HDMI connected, both
sources connected, USB disconnect/reconnect, unsupported modes and a new
source-built image. Persistent device-path CLI schema changes are staged in
the source tree but have not been installed into the live CLI reference tree.
CSI/provider initialization and general hardware-converter negotiation remain
future work; RGA selection is currently scoped to the tested ROCK RGB path.

USB reconnect live check: after the user unplugged/reconnected the Elgato USB
cable (HDMI left attached), systemd restarted the capture process automatically.
The shared selector recovered the same by-id capture node, selected NV12 and
FFmpeg/MPP resumed 1920x1080 H.264 streaming. No manual service restart was
performed for recovery. This verifies USB recovery for the FFmpeg path only;
visual confirmation after recovery is tracked separately.

The user also confirmed the desktop returned after USB reconnect. Next, with
Elgato USB removed and the source moved to ROCK HDMI-IN, automatic selection
changed to stream_hdmirx (/dev/video0), reported signal present and selected
BGR3 for FFmpeg. The user confirmed the picture returned without manual service
intervention; video and local-input services were active.

Internal HDMI native CLI backend checks also passed with the shared selector:
GStreamer launched BGR -> v4l2convert (Rockchip RGA) -> NV12 -> mpph264enc,
with 121 decoded 1080p frames in the short two-second RTSP probe. uStreamer
launched with --format=BGR24 and reported online 1080p/60 capture fps. These
are technical stream checks, not new visual colour/latency confirmations.
FFmpeg/8000 kbit/s/GOP 60 was restored after the checks.

Multi-device selection check: with internal HDMI carrying the signal and the
Elgato attached by USB without HDMI, discovery returned exactly two capture
sources (no metadata sibling). Internal HDMI reported present; Elgato reported
unknown, not absent. Both selection with remembered state and a fresh selection
chose internal HDMI. The running FFmpeg stream continued decoding at 1080p.
This was a read-only selection check, not a reboot or a test with two valid
HDMI signals.

### Capture selection interface

Omitting `video device` enables automatic source selection. Explicit
`/dev/videoN`, `/dev/v4l/by-id/...` and `/dev/v4l/by-path/...` selections are
accepted by the source-built CLI. The new `show kvm-over-ip` operational
command displays the last selection plus service/process state; a remembered
signal value is not presented as a current live measurement. These XML changes
require the next source-built package, not edits to generated CLI caches.

Format choice now filters discrete modes by requested size/rate (including
fractional-rate tolerance), checks detected HDMI size/rate and uses the
non-mutating V4L2 TRY_FMT ioctl for explicit resolution requests. Incompatible
requests fail with an error rather than silently changing capture size. Where
drivers do not enumerate frame intervals, runtime negotiation still determines
whether a requested rate can be delivered; configured rate is not measured fps.
Conversion is visible in the video service's process command line.

Capture helper, CLI, source-profile, kernel-profile and supervisor tests pass,
as do both CLI XML schemas against the locally available upstream schemas.
No new kernel/image build has been performed for this changeset. Live helper
updates have been applied; new XML command/path handling awaits package build.
