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
