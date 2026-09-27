# Mesa connection to Panthor cached maps — 2026-09-27

Research only; no runtime replacement or new build started.

## Confirmed upstream implementation

The Linux dri-devel v8 cover letter explicitly points to PanVK MR36385:
https://www.mail-archive.com/dri-devel@lists.freedesktop.org/msg579708.html
https://gitlab.freedesktop.org/mesa/mesa/-/merge_requests/36385
GitLab's web page was blocked by its anti-bot page. Read the upstream commits
through the GitHub Mesa mirror and cross-checked official Mesa release notes:
https://docs.mesa3d.org/relnotes/26.0.0.html

The series is already in Mesa26.0.0 (2026-02-11), not merely an unmerged proposal:
- b5e47ba8941467a4e2f53907a6645a0703852e62: BO CPU mapping synchronization helpers.
- a32eb87a5dbfab320f3d24c5d94505b11a66e3dc: PanVK Flush/InvalidateMappedMemoryRanges.
- 1c7793ea0bba93295ed6149152d00e5efa8a7267: HOST_CACHED memory types.
These commits identify MR36385 and landed 2025-12-12. Use the full compatible
series/release, not just the allocation flag: noncoherent CPU/GPU caches require
correct flush/invalidate operations.

Verified at tag mesa-26.0.0:
https://github.com/chaotic-cx/mesa-mirror/blob/mesa-26.0.0/src/panfrost/lib/kmod/panthor_kmod.c
The device-props code advertises WB_MMAP for DRM Panthor1.7+, matching the version
reported by our new test kernel. Version match alone does not validate the
backport's complete semantics.
https://github.com/chaotic-cx/mesa-mirror/blob/mesa-26.0.0/src/panfrost/vulkan/panvk_device_memory.c
PanVK requests WB_MMAP for the appropriate memory type and implements cache
maintenance. Exported buffers deliberately avoid cached allocation in this path.

## OpenGL limitation

Verified at mesa-26.2.0:
https://github.com/chaotic-cx/mesa-mirror/blob/mesa-26.2.0/src/gallium/drivers/panfrost/pan_bo.c
`to_kmod_bo_flags` maps EXECUTABLE, ALLOC_ON_FAULT and NO_MMAP; it does not request
WB_MMAP. Current checked pan_resource.c likewise did not expose this option.
Thus a generic 'upgrade Mesa' does not establish cached CPU readback for native
Panfrost OpenGL. Our measured Mesa25.0.7 KMS path stayed ~14fps/~291ms with the
new kernel, consistent with that limitation, but not proof of the exact slow
function (instrumented Sunshine will locate it).

## Concrete next candidates

1. Isolated Mesa26.x runtime with Panfrost, PanVK and Zink, same old runtime kept.
   First verify EGL/DRM import, actual render device and image correctness.
2. Native Panfrost versus Zink-over-PanVK for Sunshine only; keep Weston/browser
   unchanged. Zink translates GL into Vulkan:
   https://docs.mesa3d.org/drivers/zink.html
   This is a candidate, not a verified Sunshine/RK3588 fix. Validate DMA-BUF
   modifiers, external-memory import, sync, HOST_CACHED staging selection and
   color/rotation. Keep MPP encoder: Vulkan rendering does not imply Vulkan Video
   encoding support. Compare same scene/rate/codec, excluding software fallback.
3. If unsupported/no gain, a native Gallium readback/staging/cache-maintenance
   implementation needs development and review; no ready verified patch found.
   Simply forcing cacheable mappings is insufficient.

## Radxa/forum cross-check

https://forum.radxa.com/t/guide-arch-linux-for-single-board-computers/26042?page=2
Maintainer reports sunshine-mpp available and room for performance improvement;
no concrete cached OpenGL fix supplied. This is firsthand experience, not proof
for our capture path.
https://forum.radxa.com/t/rk3588-and-mainline-kernel-video-problems/30762
RK3588/mainline graphics discussion, not a matching validated KMS readback fix.
https://docs.radxa.com/en/som/cm/cm5/radxa-os/mali-gpu
Distinguishes proprietary Mali and Mesa/Panthor stacks. Its Bookworm capability
table must not be generalized to current PanVK; upstream documents G610 Vulkan:
https://docs.mesa3d.org/drivers/panfrost.html
No reason from these sources to replace our working kernel with a vendor stack.

## Live validation: Mesa 26.1.6, 2026-09-27

Isolated runtime `localhost/vyarm-kiosk:mesa26-probe-20260927`, image ID
`e07845534a672ccb9cc6810cc6a3bd14f6b38d273565d12eb61fd6cce8e4c97d`.
Based on the known Sunshine `audio-hevc-test3-20260927` runtime; upgraded only
container Mesa packages from Debian trixie-backports to 26.1.6-1~bpo13+1.
Host and running kiosk graphics libraries untouched. No reboot or Chromium build.
Kernel remains `6.18.50-vyos-panthor-cache-test` for this comparison.

- Vulkan: actual Mali-G610 MC4, MESA_PANVK, Vulkan 1.4.354; HOST_VISIBLE |
  HOST_CACHED memory type available. This does not prove Sunshine uses it.
- Native EGL: Mali-G610 MC4 (Panfrost), OpenGL 3.1 Mesa26.1.6.
- Native KMS streaming, HEVC/rkmpp, 1920x1080, requested30fps, 2Mbps,
  40-second client window: incoming13.81fps, rendering13.72fps,
  host latency248.1/306.6/290.5ms min/max/mean; network1ms, network loss0%,
  jitter drops0.61%; hardware client decoding1.11ms.
  Earlier same-kernel Mesa25 measurement:14.33fps, mean host290.8ms.
  No material performance gain; not a controlled content-identical benchmark.
- Zink explicitly selected with MESA_LOADER_DRIVER_OVERRIDE=zink,
  GALLIUM_DRIVER=zink and VK_DRIVER_FILES pointing to panfrost_icd.json.
  EGL confirms actual Zink over MESA_PANVK, not lavapipe, but only GL2.1/ES2.0.
  Sunshine fails EGL context creation with0x3009 (EGL_BAD_MATCH), then cannot
  find a usable video path. No valid Zink stream or performance measurement.
  PanVK does not advertise VK_EXT_transform_feedback in this build. Mesa's
  Zink requirements list it for GL3.0; upstream Sunshine graphics.cpp requests
  OpenGL context major3. These observations explain the compatibility boundary.
  No version override was used to pretend missing GL support exists.

References for the context/feature boundary:
https://docs.mesa3d.org/drivers/zink.html#opengl-3-0
https://github.com/LizardByte/Sunshine/blob/master/src/platform/linux/graphics.cpp

Tests stopped; normal `kiosk` remained running. Test image retained for follow-up.
Evidence outside git (client logs may contain authentication data):
`work/panthor-live-36335262291/stream-mesa26-native.log`,
`sunshine-mesa26-native-summary.log`, `sunshine-mesa26-zink-summary.log`,
`mesa26-device-check.txt` under the local Codex workspace.

Next useful step: instrument native Sunshine capture/import/readback separately
from CPU conversion and MPP encode. The GitHub instrumented-runtime build passed
its Sunshine step and was assembling the image during this test. A generic Mesa
upgrade or Zink default is not justified by these results. Physical color/rotation
validation of the Mesa26 stream was not performed by the user.
