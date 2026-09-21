# Isolated Hantro AV1 live probe, 2026-09-21

## Status: experimental, NOT enabled in production

ROCK 5B, running 6.18.50-vyos-f-test3. Matching local Image SHA256:
`116362b890cc0343799564401ec682a7e1fb1a770db3fc51a7297bd9abf5bbc3`.
The existing kernel has MODVERSIONS and mandatory module signatures, but no
Hantro module. Built Hantro and v4l2-jpeg externally from its exact source/output
trees without editing the kernel configuration. Signed with the existing kernel
build key (private key remains outside the repository).

AV1 DT node fdc70000 was already enabled; compatible rockchip,rk3588-av1-vpu.
No CMA reservation (CmaTotal 0) and no IOMMU association on that node.
Prevented unrelated G1 fdb50000 binding with a temporary driver_override.
The module additionally bound VEPU121 fdba0000; explicitly unbound that device.
AV1 appeared as video4/media2. Existing video0/1/2 remained available.

## Results

* GStreamer 1.28.7 v4l2slav1dec decoded the 5-second 1080p60 AV1 fixture
  through EOS in approximately 3.31 seconds with fakesink, sync=false.
  This is a short decoding probe, not a browser/display performance result.
* Two fdsink runs yielded 300 frames each in NV12_4L4, not linear NV12.
  Comparing these raw hashes with FFmpeg linear NV12 was invalid. Do not
  interpret the initial zero matches as a decoder correctness failure.
* Adding videoconvert to linear NV12 failed source-buffer allocation.
  Thus the lack of reserved contiguous memory remains a real test concern,
  despite the initial decoder-only success. Exact allocation cause unconfirmed.
* An external untile/hash run completed with exit 0. Its hashes remain on ROCK;
  final comparison has NOT been retrieved or verified.
* Chromium 153/Weston 16, sandbox enabled, two independent runs: initially
  selected V4L2VideoDecoder, then initial-decode-error fallback to Dav1d.
  Both ended with 300 total frames, 9 dropped frames, platform decoder false.
  These are SOFTWARE playback results. See browser-results.json.
* Chromium source has no NV12_4L4/VT12 mapping in the examined Fourcc and
  image-processor paths. Tiled-output import is a candidate blocker, not yet
  isolated as the sole cause of the runtime fallback.

## Cleanup interruption / follow-up required

A 12-minute systemd rollback timer was armed before loading modules. An explicit
rollback was invoked about 23:37 CEST after the tests. That SSH call did not
return; subsequent ping/SSH failed (host unreachable). ThinkPad stayed on its
home LAN and the NUC remained reachable. Driver-unload hang versus power/LAN
loss is NOT established. User was asked for physical status. Do not claim
rollback completed or that the production kiosk is currently healthy.

Modules were loaded with insmod only, not installed into /lib/modules or boot
autoload configuration. No kernel/image replacement or reboot was performed.
Live artifacts: /config/kiosk-test/kernel-test3/hantro-av1-live.
The rollback script removes the test container, rmmods hantro_vpu/v4l2_jpeg,
and clears G1 driver_override. Inspect logs and module/device state after
connectivity returns; avoid another unload test until the cause is understood.

## Reproduction notes

External build directory contains copied drivers/media/platform/verisilicon as
hantro/ and drivers/media/v4l2-core/v4l2-jpeg.c. Top Makefile:

```make
obj-m += v4l2-jpeg.o
obj-m += hantro/
```

Build with exact matching SOURCE and KBUILD (including Module.symvers):

```sh
make -C "$SOURCE" O="$KBUILD" M="$TEST_BUILD" \
 ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
 CONFIG_VIDEO_HANTRO=m CONFIG_VIDEO_HANTRO_ROCKCHIP=y \
 KCFLAGS=-DCONFIG_VIDEO_HANTRO_ROCKCHIP=1 -j2 modules
```

AV1 WebM fixture was remuxed with ffmpeg -c copy -f obu, because this GStreamer
image does not include matroskademux. Decode pipeline: filesrc ! av1parse !
v4l2slav1dec ! fakesink (or fdsink). Hash helper is restricted to tightly packed
1920x1080 NV12_4L4; its layout follows the matching kernel documentation
Documentation/userspace-api/media/v4l/pixfmt-yuv-planar.rst, 4x4 linear tiles.
It must NOT be reused blindly for padded buffers, other sizes, or 10-bit data.

Next: recover/verify host state, retrieve final hashes and kernel logs, identify
Chromium initial-decode failure precisely, then evaluate format conversion and
contiguous-memory/IOMMU allocation. VP9 remains a separate driver investigation.

## Recovery verified after user power cycle, ~23:46 CEST

LAN SSH returned, kiosk-test container running. No persistent pstore crash record.
G1 driver_override reset to (null); AV1 test video4 absent. The final untiled
JSON is zero bytes after reboot, so no final comparison is recoverable from it.
Earlier hardware/software hash files survived. Previous journal ends at 23:37:20
without an explicit panic/unload backtrace; driver teardown remains suspected,
not proven. No further module loading/unloading performed in this follow-up.
