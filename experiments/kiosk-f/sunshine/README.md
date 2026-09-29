# Experimental Sunshine MPP backend

Not enabled in released images. The patch is under test, not evidence of working
Sunshine hardware encoding. Keep the original kiosk image and paired identity.

Pinned inputs:

- Sunshine: `63d35f702ee9e362e43263742981836ec0710384`
- Rockchip MPP: `c08762ebfadeb4e986d2fed993bc7a54862d3ebe`
- ffmpeg-rockchip: `d90e3a1c18d7929383cf88c1b3da2e2d1c966cbf`

`Containerfile.build` builds the encoder dependencies. `Containerfile.sunshine`
expects an archive containing `source/`: the pinned Sunshine checkout, recursive
submodules, and `0001-add-rkmpp-encoder.patch` applied. Exclude `.git` directories.
Build the dependency image as `localhost/vyarm-sunshine-builder:mpp` first.
The second build compiles the binary only; existing matching web assets are retained.
Mount a persistent build directory at `/buildcache` for the second build so
failed attempts retain completed object files. Use a single compiler process:
the initial two-process build exceeded a 3 GiB cgroup limit while compiling
`nvhttp.cpp`. The retry uses one process and a 4 GiB limit on the 8 GiB test host.
MPP, FFmpeg and patched Sunshine have built successfully. The live native VyOS
container now auto-selects h264_rkmpp. An actual Moonlight session logged both
`Video encryption enabled` and `Creating encoder [h264_rkmpp]`.
An isolated test without the MPP device selected libx264 successfully.
Perceived smoothness, frame-time comparison and reboot testing remain pending.

The backend uses upstream encoder validation and software fallback. It does not
select by board name. Only H.264 SDR 8-bit 4:2:0 is declared; HEVC, AV1, HDR and
4:4:4 are not claimed. CPU capture/color conversion remain separate bottlenecks.
Do not equate an MPP-capable SoC with a tested kernel/userspace/device combination.

Before activation, verify linked libraries, restrict access to the MPP device,
back up the current configuration, and retain the original image. Required tests:
startup probe, actual paired Moonlight stream, CPU/frame-time measurements,
forced software fallback, stop/start, and no regression of local kiosk input.
Do not expose the management interface or change pairing identities for this test.

Security source review at the pinned Sunshine revision confirms
`lan_encryption_mode = 2` and `wan_encryption_mode = 2` require encryption.
These settings still need a real client connection test. Browser certificate
trust is a separate issue from stream encryption; management currently uses SSH
port forwarding to a host-loopback listener.

## Container hardware description

`0002-mpp-container-compatible-path.patch` adds an optional
`MPP_DEVICE_TREE_COMPATIBLE` path to MPP. The default upstream path remains
unchanged. The runtime image points it at `/run/mpp/compatible`, populated by a
read-only native VyOS volume from `/sys/firmware/devicetree/base/compatible`.
This avoids unmasking firmware in Podman or adding a board-name lookup table.
Only the MPP library needs recompiling for this adjustment, not Sunshine.

The kiosk entrypoint assigns the explicitly mapped `/dev/mpp_service` to the
video group with mode 0660. Sunshine runs as kiosk, a video-group member.
Existing SYS_ADMIN for Xorg remains a separate review item; the container is
not configured as privileged. Input event4 warnings still need the generic USB
work; MPP success does not imply those are resolved.

## Live activation and rollback

The live test uses image `localhost/vyarm-kiosk:mpp-test`, native device mapping
`video-encoder`, and read-only volume `mpp-compatible`, committed and saved.
Sunshine encoder selection is automatic (no encoder override). LAN and WAN
encryption modes are both 2; the real client connection confirmed encryption.
The original image `localhost/vyarm-kiosk:test-20260919` remains available.
Backups on the ROCK under `/config/kiosk-test/` include
`sunshine.conf.before-mpp`, `start-kiosk.before-mpp` and `config.boot.before-mpp`.
No pairing identity or private key has been copied into this repository.

To revert only this experiment, restore the two backed-up service files, set
the native container image back to the original image, delete `video-encoder`
and `mpp-compatible`, then commit/save. Do not load the full configuration backup
after unrelated router changes. No host image rebuild or reboot was required.

Initial live-session CPU sample: 12 seconds using /proc process counters,
100% = one CPU core: Sunshine 66.6%, Xorg 40.6%, Chromium processes combined
21.9%. This is an observational sample, not a controlled latency/FPS benchmark
or a like-for-like software-versus-MPP comparison.

## Follow-up conversion probe

A missing `/dev/rga` did NOT imply that RGA was unavailable. The live kernel
has CONFIG_VIDEO_ROCKCHIP_RGA=m and a bound rockchip_rga V4L2 memory-to-memory
device (currently /dev/video0; production discovery must not hardcode that number).
It advertises XR24 input and NV12 output. A bounded v4l2-ctl mmap test converted
60 synthetic 1920x1080 frames and exited 0. This is a feasibility test, not a
measured end-to-end speedup or verified color-accuracy test. Sunshine still uses
CPU color conversion. GPU rendering remains separate; Panfrost/Panthor are not
enabled in this kernel.

X11 advertises MIT-SHM; active shared-memory capture needs confirming during a
stream. The V-Sync-only Moonlight comparison is pending user feedback; resolution,
stream frame rate, minimum FPS and frame pacing were not changed for these probes.

## RGA color validation: activation blocked (2026-09-20)

`probe-rga-colors.py` discovers the RGA node through sysfs and checks mem2mem,
streaming and pixel-format capabilities before sending synthetic color bars.
It does not open the HDMI receiver, change native container configuration or
restart Sunshine. It requests full-range BGR0 input and limited-range NV12
output at 1920x1080. Run with device access, e.g.:

```
sudo python3 probe-rga-colors.py
```

On ROCK 5B, kernel 6.18.50-vyos, RGA HW version 0x03.02, this test fails:
BT.601 maximum sampled channel error 20; BT.709 error 16 (8-bit levels).
BT.601 black/white Y is 0/255 instead of 16/235. The negotiated output reports
quantization Default despite the explicit limited-range request. BT.709 red Y
is 54 rather than 63, and green is 182 rather than 173. The reference formula
was independently checked using local FFmpeg/libswscale on the same raw bars.
Exact device output is in `test-results/rock5b-rga-colors-20260920.json`.

The real Sunshine session currently requests Rec.601/MPEG (limited range), so
using this output unchanged would mismatch stream color metadata. No RGA path
has been activated or added to Sunshine yet. MPP hardware encoding remains in
use; capture/color conversion remains CPU-based. Resolution, requested FPS,
Moonlight settings, pairing and network configuration were not changed.

Next investigate the kernel driver/SoC CSC register behavior and quantization
handling, then rerun this test before integrating persistent V4L2 queues into
Sunshine. Merely relabeling the encoded frame as another color space is not a
fix. A future converter must validate supported color matrix/range and fall
back to swscale for unsupported combinations or failed device operations.
The limited test patterns here are an initial rejection gate, not proof of
complete color correctness or performance. No speedup is claimed.

Upstream source reference (not proof of the exact running build's root cause):
https://github.com/torvalds/linux/blob/v6.18/drivers/media/platform/rockchip/rga/rga-hw.c

### Follow-up source investigation

The manufacturer's current librga FAQ maps RGB-to-YUV BT.601 limited range to
mode 2, and full range to mode 1. The upstream v6.18 RGA header labels its
BT601_R0 destination mode as 1, which the driver chooses by default. This
matches the observed full-range BT.601 output and gives a specific driver-level
lead. It is not sufficient to infer a tested fix for BT.709 or all supported
SoCs. Do not change source-side YUV-to-RGB constants as part of a destination
RGB-to-YUV correction. Quantization negotiation also needs proper implementation.

Source: https://github.com/airockchip/librga/blob/main/docs/Rockchip_FAQ_RGA_EN.md
(Q2.14). Compare drivers/media/platform/rockchip/rga/rga-hw.{c,h} in Linux v6.18.

The running host has no /usr/src headers or /lib/modules/6.18.50-vyos/build.
The matching release exposes kernel.config but not Module.symvers or a prepared
module build tree. The local old 6.18.44 tree is not a compatible substitute.
A live driver replacement therefore needs a matching prepared kernel build and
symbol versions first; no force-loading or unverified binary patch was attempted.
No kernel module, container configuration or display mode was changed by this
investigation. Once a correctly built test module is available, preserve the
stock module and retest both matrices/ranges before Sunshine integration.
