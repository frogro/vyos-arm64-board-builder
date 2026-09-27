# KMS capture latency: research, 2026-09-27

## Local evidence

See latency-comparison-20260927.json and ../ACCEPTANCE-FOLLOWUP-20260927.md.
Same Sunshine binary: X11 capture ~56 fps/36 ms host processing at portrait60;
KMS on either X11 or Wayland ~13–14 fps/278–281 ms at requested30.
Animated X11/KMS reproduces the issue. Capture thread consumes ~97% of one CPU.
This identifies capture as the leading suspect, not an individual function yet.
No new live modifications were made for this research.

## Sources and applicability

1. Sunshine v2026.914.233613 kmsgrab.cpp, display_ram_t::snapshot:
   https://raw.githubusercontent.com/LizardByte/Sunshine/v2026.914.233613/src/platform/linux/kmsgrab.cpp
   Imports the framebuffer into EGL, then calls GetTextureSubImage into CPU RAM.
   Measure refresh/import/readback/cursor separately. Hardware MPP encoding alone
   does not eliminate this readback. Renderer must be logged inside Sunshine;
   standalone probes with missing supplementary groups can falsely show llvmpipe.

2. dri-devel: [PATCH v8 00/13] drm/panfrost, panthor: Cached maps and explicit flushing:
   https://www.mail-archive.com/dri-devel@lists.freedesktop.org/msg579708.html
   Write-back mapping patch:
   https://www.mail-archive.com/dri-devel@lists.freedesktop.org/msg579711.html
   Explicitly targets inefficient CPU reads of uncached GPU buffers. Dependencies
   include coherency reporting, BO_SYNC, BO flag queries and cache maintenance.
   Local tmp/av1-iommu-test4/source/include/uapi/drm/panthor_drm.h lacks
   DRM_PANTHOR_BO_WB_MMAP, DRM_PANTHOR_BO_SYNC, DRM_PANTHOR_BO_QUERY_INFO.
   This checks that source tree, not the provenance of every running kernel.
   Runtime Mesa previously measured as 25.0.7-2+deb13u1.
   Cover letter links PanVK MR36385:
   https://gitlab.freedesktop.org/mesa/mesa/-/merge_requests/36385
   MR access denied during research. Crucially, PanVK is Vulkan whereas current
   capture uses OpenGL/Panfrost. Do not assume adding the kernel series alone
   improves this path. Audit OpenGL driver use and upstream merge state first.

3. Sunshine issue4906 and PR4967:
   https://github.com/LizardByte/Sunshine/issues/4906
   https://github.com/LizardByte/Sunshine/pull/4967
   KMS cursor-related CPU/stuttering report; fix corrects minimum_fps_target,
   duplicate-frame timing and queue timeout behavior. Merged 2026-04-19 as
   44bf39be75adc063a4a35f8b0f065404c6c9971d. GitHub compare API confirms tag
   v2026.914.233613 is ahead410/behind0 of that commit. Already in upstream base;
   not a missing patch to reapply. Our animation test also reproduces without
   cursor interaction and KMS reports no cursor plane.

4. Official Sunshine troubleshooting:
   https://github.com/LizardByte/Sunshine/blob/master/docs/troubleshooting.md
   Missing CAP_SYS_NICE can prevent high-priority EGL contexts and cause drops
   under GPU load. Our logs report missing capability with MEDIUM priority;
   documentation describes HIGH. Lower-confidence, cheap isolated A/B test,
   not proof that granting capabilities fixes readback throughput.

5. Forum first-person comparison:
   https://www.reddit.com/r/linux_gaming/comments/1fs0dgh/
   AMD KMS host latency/low-fps report includes encoder/library issues. Different
   GPU and encoding path; corroborates symptom only, no validated RK3588 fix.
   Targeted Armbian/Radxa searches did not establish a matching confirmed fix.

## Next bounded experiments

- Instrument actual Sunshine capture: GL_VENDOR/GL_RENDERER, DRM/render node,
  per-stage monotonic timings, framebuffer format/modifier and dimensions.
- Compare CPU readback formats and staging/copy behavior only after locating
  the expensive stage; keep the historical X11 path as the control.
- One isolated CAP_SYS_NICE comparison with identical scene/codec/rate.
- If CPU buffer access is dominant, audit Panthor cache series plus its actual
  OpenGL userspace counterpart. No blind cached mapping without synchronization.
- Longer-term DMA-BUF-to-RGA/MPP path could avoid CPU readback, but needs format,
  modifier, fence and lifetime handling. Existing CPU-buffer RGA converter is
  not automatically such a zero-copy path.
- Portal/PipeWire is a separate possible capture architecture, not a drop-in
  Weston configuration switch. No performance claim without implementation/test.

No new kernel patch or main-branch change is justified solely by these sources.
