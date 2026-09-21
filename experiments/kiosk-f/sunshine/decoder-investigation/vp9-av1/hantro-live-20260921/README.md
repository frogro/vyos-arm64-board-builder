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

## Corrected module live tests, 2026-09-22 00:00 onward

Booted the existing one-shot test3 entry; GRUB next_entry verified empty after
boot. Production default preserved. Signed the PM teardown backport with the
matching existing test3 key. Prevented unrelated G1/VEPU bindings before load.

* Three explicit load/unload cycles completed; further cleanup cycles also
  completed after decode and browser probes. No repeat of the earlier freeze.
* Hardware AV1 decoder -> direct linear NV12 caps -> fdsink: **300/300 frames
  bit-identical to FFmpeg software reference**, including count and order.
  See fixed-nv12-hashes.json (both complete SHA256 lists). No videoconvert.
* Chromium diagnostic run: NV12 output candidate, 10 MMAP capture buffers,
  V4L2VideoDecoder, platform=true, ended/300 frames, 41 dropped. Hardware
  browser decode works in this run, but 1080p60 performance is NOT confirmed.
* Earlier browser fallback remains incompletely explained: fresh boot changes
  memory availability; PM patch does not itself demonstrate a decoding fix.
* Device probing is asynchronous: udevadm settle alone did not guarantee the
  media/video devices existed. Updated probe waits for actual nodes, derives
  their numbers from AV1 platform device, and guards the kernel release first.

Modules unloaded and unrelated driver overrides restored after each completed
probe. Kiosk container continued running; no full-image/production integration.

### Remaining power-domain failure; repeat stopped

The no-verbose repeat did not start playback: AV1 device readiness failed.
Kernel reports `failed to get ack on domain 'av1', val=0xa9eef` repeatedly
following removal/reload. This was also present around early lifecycle probes.
Therefore the three successful insmod/rmmod command pairs must NOT be called
three clean hardware power cycles: binding is asynchronous and warnings remain.
The PM backport prevented the observed system freeze in these attempts, but
does not establish reliable remove/reprobe. Investigate reset assertion versus
power-domain sequencing (including Collabora power-domain fixes) before more
live churn. Readiness guard now stops before decode when nodes are absent.

Final check ~00:05: host reachable, kiosk-test running, no hantro_vpu/v4l2_jpeg
loaded, five temporary driver overrides all (null), only production container
running. Test3 kernel still running; next normal boot uses unchanged production
default. All experimental AV1 modules remain opt-in, no image recipe changes.

## PM-stage diagnostic module, 2026-09-22 00:16 CEST

Single initial load/unload followed by one reload, without opening the decoder
or starting video playback. Kernel journal streamed over SSH to the ThinkPad;
see pm-stage-live-transcript.txt. Matching signed test3 module, unrelated Hantro
platform nodes blocked temporarily as in the earlier probes.

* First load registered AV1 as video3. All remove-stage markers completed,
  including reset assertion; rmmod returned. No ACK warning in this first cycle.
* Reload 43 seconds later emitted the AV1 ACK timeout (val=0xa9eef). No AV1
  video node appeared, and no diagnostic probe/runtime-PM marker appeared.
* Second rmmod returned without remove-stage messages. This is NOT a second
  successful hardware cycle: the driver had not registered the AV1 device.
* Host remained reachable; kiosk-test remained running. Both experimental
  modules were removed and all six checked overrides read (null). No reboot,
  image/default changes, or further retries after the reproduced warning.

This reproduces the lifecycle failure independently of Chromium, codec input,
and decode buffers. The first probe marker is NOT at function entry: it is
immediately before runtime-PM setup. Thus the log alone does not prove that
hantro_probe was never entered. platform_probe attaches/powers the PM domain
before calling the driver's probe, making domain attach a strong next suspect;
confirm with entry/attach tracing before attributing the exact call path.
The ACK message still omits idle direction and expected mask. Next diagnosis
should expose those values and power-on/off context in the PM-domain driver
(or existing kernel tracing), without changing reset/power sequencing blindly.
The PM teardown backport remains experimental; this test is not a fix.

## Existing-kernel argument tracing, 2026-09-22 00:20 CEST

Used temporary kprobes in an isolated trace instance, without changing kernel
code or power/reset behavior. ARM64 x1 records the second argument at entry;
kretprobes record signed return values. Probe definitions:

```
p:vyarm_av1_diag/idle rockchip_pmu_set_idle_request idle=%x1:u8
p:vyarm_av1_diag/power rockchip_pd_power power_on=%x1:u8
r:vyarm_av1_diag/idle_return rockchip_pmu_set_idle_request ret=$retval:s32
r:vyarm_av1_diag/power_return rockchip_pd_power ret=$retval:s32
```

First traced load registered video3 and completed remove without warning.
Following reload reproduced the AV1 ACK warning. In that insmod task (PID 68155):
power_on=1 -> idle=0 -> idle return -110 -> power return -110, followed by
power_on=0 cleanup. This establishes failure while powering on/leaving idle,
not requesting idle on power-off. Trace also contains unrelated successful
power-domain activity; the probes did not record domain names. Association with
AV1 is supported by the sole matching kernel ACK error and failed AV1 probe.
See av1-power-trace-success.txt and av1-power-trace-reload.txt.

A successful retry after the previous failure also shows the device is not
permanently stuck until reboot. This does not prove a timing-only cause.
No decode was attempted. Temporary probes and trace instance removed, modules
unloaded, overrides restored; kiosk-test still running. No electrical supply
measurement was made. Reset/BIU versus power-on sequencing remains the next
causal investigation; do not treat this as a verified hardware or PSU defect.

## Opt-in reset causal test, 2026-09-22 00:22–00:52 CEST test window

Built a separate signed module with the existing PM-order backport and markers.
The added module parameter `vyarm_test_keep_av1_reset_deasserted` defaults false,
is read-only after load, and only affects rockchip,rk3588-av1-vpu remove.
When enabled, it omits the final reset assertion. No image/autoload integration.
This is a causal experiment, not a production-ready reset policy.

Initial candidate: three clean cycles. Same binary with parameter=0: first
cycle registered/removed, second failed device readiness with the AV1 ACK
warning. Candidate parameter=1 again: five clean cycles. Results support the
final reset assertion as a causal contributor. They do not isolate core versus
BIU lines, prove all error/recovery paths, or qualify other SoCs.

Three subsequent short decode runs: each 300/300 linear NV12 frame hashes match
the existing FFmpeg reference. See reset-hash-comparison.json.

Long fixture is the same five-second AV1 sample concatenated 24 times using
FFmpeg stream copy: 119.999 seconds / 7200 frames, 1920x1080, 60fps. This exercises
sustained/repeated use, not diverse AV1 bitstreams or 10-bit/film-grain conformance.

Chromium + headless Weston GL, separate sandboxed processes: all three runs
ended with 7200 total frames and V4L2VideoDecoder/platform=true. Drops:
1023 (14.21%), 1096 (15.22%), 996 (13.83%). Mali-G610/Panfrost/ANGLE renderer.
Original kiosk kept running. One brief stream-copy preparation and a failed
Python-GI availability probe overlapped the browser series; these are practical
live-system measurements, not controlled performance benchmarks. Temperature
readings during playback reached approximately 89C; no CPU cooling device was
listed, and frequency limits still showed the configured maxima. Thermal
influence is not ruled out. Do not attribute all drops to a specific component.

GStreamer same long stream, v4l2slav1dec -> NV12 -> fakesink(sync=false):
7200 rendered, zero sink-dropped frames in each of three runs. Pipeline times
35.914 / 36.152 / 36.120s (~199–200fps). Hardware decoding therefore has >60fps
throughput for this fixture outside the browser output path. This does NOT
prove Chromium's own decoder/pool path is equally fast. The ctypes helper reads
GstBaseSink stats after EOS; it does not hash these long-run frames. `/usr/bin/time`
on Podman measures the client, not aggregate container CPU: do not quote its
CPU percentage as decoder CPU load. AV1 domain read off-0 after each run.

See source crosscheck for vendor reset ownership. Keep this experimental until
reset-line isolation, error recovery, reboot and other-board validation exist.

Extended idle cycles: six clean register/remove/re-register cycles with 1, 5,
15, 30, 60 and 120 second dwell both before and after remove. Every measured
before/after power state was off-0. No ACK warning; each cycle verified a real
AV1 device node, not just insmod exit status. See reset-idle-cycles.txt.

An additional 120s browser run with --disable-gpu-vsync and
--disable-frame-rate-limit did NOT report ended before the 150s probe deadline;
last sampled page state was playing (hardware decoder still reported). No valid
completed-run drop percentage is available. These flags are not an improvement
established by this test and are not adopted. A subsequent intentional 15s
probe closure completed and AV1 returned to off-0; full recovery playback follows.

Patch replay check: applying the PM-order, stage-diagnostic and reset-causal
patches in that order to pristine test3 hantro_drv.c produces exactly the
compiled test source. Shell syntax and Python compilation checks passed.

Final full recovery run after intentional early closure: ended, 7200 frames,
923 dropped (12.82%), V4L2VideoDecoder/platform=true. Successful recovery does
not resolve output pacing. Only ACK warning in this test window was the
parameter=0 control at 00:24:54. Final live check ~00:51: no hantro_vpu or
v4l2_jpeg loaded, all six overrides (null), AV1 off-0, only kiosk-test container
running, GRUB next_entry empty. No reboot or persistent boot/image changes.

Next: isolate the BIU reset lines from decoder-core resets in a separately
reviewable test, then test error recovery/reboot before proposing an opt-in
image patch. Preserve original reset handling for other compatibles. Browser
output/pool performance remains separate; no new CLI/default is justified yet.
The existing NUC Chromium build continued under its monitor during this test
window; no restart was required (still unfinished).
