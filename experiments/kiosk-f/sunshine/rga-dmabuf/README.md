# RGA DMA-BUF feasibility, 2026-09-27

Experimental standalone probe; no production setting or main change.

**Correction after live follow-up:** FULL_CSC IS present in the running module.
`experimental_full_csc` was N during the initial tests below. The old test4 source
inspection was not proof of the final module contents. Enabling the existing
revision-gated parameter makes both probes pass. No missing kernel patch or
kernel rebuild was required; see follow-up below.

## Actual Sunshine test

Same Mesa26 runtime / Panthor test kernel as MESA-CACHE-RESEARCH-20260927.md.
Enabled `SUNSHINE_VYARM_RGA_TEST=1` in an isolated Sunshine process; HEVC/rkmpp,
KMS1920x1080, requested30fps,2Mbps,40-second Moonlight window. Server confirmed
120/120 RGA frames,0CPUfallback. Incoming15.90fps,rendered15.79fps,mean host265.9ms
(min242.2,max275.7),network1ms,network loss0%,jitter drops0.53%.
Earlier CPU conversion run:13.81fps,290.5ms. Single short runs, not statistically
controlled identical-content benchmarks. **Color validation below fails on this
kernel, so these timings do not constitute a successful quality acceptance.**
Existing RGA conversion still follows GL readback; it does not bypass that stage.

## Direct path feasibility

Live DRM state: Weston primary plane XR24,1920x1080,pitch7680,
modifier0x0800000000000051 (ARM AFBC). The inspected V4L2 RGA driver implements
linear formats and no AFBC modifier negotiation. Do not feed that framebuffer
as linear RGB. A direct KMS-to-RGA implementation needs compatible linear buffers
or a GPU decompression/staging step; compositor restart/AFBC disabling was not
performed in this experiment.

`probe.cpp` checks a narrower prerequisite: import a synthetic linear RGB DMA-BUF
into RGA, convert to NV12, dequeue and copy output, validate eight colors. Source
CPU access is synchronized; both queues are stopped before unmapping/closing.
Per-frame deadline200ms; run under external timeout30s as well. Device discovered
by sysfs driver name; no fixed video number. It is NOT a KMS capture integration,
NOT a direct MPP encoder path and NOT an end-to-end zero-copy claim.

Build in disposable trixie container:
`g++ -std=c++17 -O2 -Wall -Wextra -Werror probe.cpp -o probe`
Run with the container's matching C++ runtime and device access:
`timeout 30 ./probe` or `timeout 30 ./probe rga-export`.
Host libstdc++ is older than the builder; initial host execution failed cleanly
with GLIBCXX_3.4.32 missing. Host libraries were not replaced.

- System heap source (`/dev/dma_heap/system`): QBUF EINVAL; kernel reports
  `swiotlb buffer is full (sz: 1048576 bytes), total 32768 (slots), used 0 (slots)`
  then `Error getting dmabuf scatterlist`. This is a DMA mapping constraint,
  not evidence that total system RAM is exhausted. Do not blindly enlarge SWIOTLB
  or DMA mask; investigate exporter segment sizes/addressability first.
- RGA MMAP allocation exported through VIDIOC_EXPBUF on a separate RGA fd:
  import works;960frames,landscape/portrait,BT601/709,limited/full.
  Conversion plus output copy~2.66–3.37ms, no per-frame RGB source copy.
  **Color errors up to20 levels**; only BT601-full passes(maxerror1).
  Complete results in results-20260927.txt. Exit2 means color mismatch.
- Original CPU-fed `rga-converter/probe.cpp`, rebuilt unmodified, also fails
  first BT601-limited case(maxerror20,4.13ms). Thus this failure is not unique
  to the new DMA-BUF input. Earlier successful results used the separately
  patched FULL_CSC module; they must not be attributed to the current kernel.

Running module:6.18.50-vyos-panthor-cache-test,HWrevision0x03.02.
The inspected test4 source rga-hw.c lacks rga_test_rgb_full_csc from
../rga-investigation/0002-experimental-rga2e-full-csc.patch. Audit final build
module provenance and include the validated CSC patch plus later multi-plane
corrections before enabling RGA by default. No module was hot-replaced here.

## Next implementation gates

1. DONE live: verify existing FULL_CSC opt-in; repeat both probes. Ensure the future
   F integration enables/checks it when the user selects experimental RGA.
2. Validate GPU import/render into an RGA-addressable linear exported buffer,
   with format/modifier support and fence/lifetime synchronization.
3. Feed RGA NV12 output to MPP with explicit colorspace/range and bounded queues.
4. Integrate opt-in Sunshine path with safe fallback, then measure real streaming.

Normal kiosk continued running unchanged. Test Sunshine and compiler containers
stopped; test binaries retained under /config/panthor-sunshine-20260927.
No images were rebuilt locally and no global Mesa/default capture changes made.


## Live follow-up: existing CSC option and GPU-to-RGA

`modinfo rockchip_rga` exposed `experimental_full_csc`; sysfs value was N.
Armed an independent eight-minute systemd rollback timer before enabling Y.
No module unload, kernel replacement, reboot or compositor restart performed.

Both original CPU-fed and DMA-BUF-import probes pass all8cases/960frames each,
maximum sampled error1. Results in csc-enabled-results-20260927.txt.
The previously observed errors were the expected legacy path with opt-in OFF,
not a regression introduced by DMA-BUF or evidence of a lost commit.

Added optional `gpu-fill.hpp`, compiled with `-DVYARM_GPU_PROBE -lEGL -lGLESv2`.
Run `RGA_PROBE_GPU=1 timeout 30 ./probe rga-export` in the isolated Mesa26 runtime.
It imports an RGA-allocated/exported linear XR24 buffer as an EGL image and renders
alternating color bars directly into it with actual Mali-G610/Panfrost OpenGL.
No RGB upload/readback through CPU memory is used in this GPU path. `glFinish`
completes GPU writes before each RGA submission. NV12 is still copied back to CPU
for validation; this is not a complete zero-copy streaming implementation.

Initial portrait4320-byte pitch was rejected by Mesa (`WSI pitch not properly
aligned`). Use storage width1088 / pitch4352, EGL image width1088, render1080 and
explicit V4L2 input crop1080. Landscape1920 already satisfies alignment.
The probe validates exact negotiated format and crop; no fake GL version.

Dynamic GPU updates on every frame: all8cases/960frames pass,maxerror1.
Mean GPU clear+completion+RGA conversion+NV12 output copy3.69–4.67ms/frame.
Source import/context setup and CPU sample checks excluded from this metric.
See gpu-dynamic-results-20260927.txt. This establishes GPU writes -> linear
DMA-BUF -> RGA feasibility, not AFBC KMS sampling or Moonlight performance.

Remaining: sample the actual AFBC framebuffer into this linear target with proper
lifetime/synchronization, then connect output to Sunshine/MPP and compare latency.
No direct current-KMS-buffer bypass was claimed or enabled by these probes.

After tests, restored experimental_full_csc=N, stopped rollback timer and removed
compiler container. Existing kiosk kept the same start timestamp throughout.

## Actual KMS AFBC source follow-up

Added `kms-source.hpp`: read-only primary-plane discovery, GETFB2, PRIME export,
EGL modifier-aware import and a GLES textured draw into the same RGA-exported
linear target. Keeps exported fd/EGL import alive through glFinish; closes GEM
handles and imports after each capture. Refuses multiple active primary planes,
changed geometry, extra planes or formats other than XR24. Does not acquire DRM
master or change display state. Current probe expects1920x1080,BT709-limited.

Build additionally needs libdrm-dev, `-I/usr/include/libdrm -ldrm`.
Run with `RGA_PROBE_GPU=1 RGA_PROBE_KMS=/dev/dri/card0 ./probe rga-export`.
The DRM node is explicitly selected for this probe; production discovery and
connector selection must be integrated with Sunshine's existing code.

Live source: Weston fb91,XR24,pitch7680,AFBC modifier0x0800000000000051.
Two120-frame runs:3.82ms then3.80ms average for KMS lookup/export/import, GPU draw
and completion, RGA NV12 conversion and output CPU copy. Per-frame metadata/import
cost included; one-time context setup and final validation readback excluded.
No per-frame RGB readback or CPU RGB upload; NV12 still copied for validation.

Final output checked against a one-time GL_RGBA readback of the linear render
target: sampled luma maximum error1, luma range17..234; chroma maximum error1
on1842flat2x2sample blocks. This checks conversion of the captured content, not
physical orientation, cursor/overlay completeness or tear-free lifetime safety.
No performance conclusion for Moonlight/MPP can yet be drawn from this isolated
capture/conversion measurement. No encoding or streaming in this probe.

Remaining work: opt-in integration with Sunshine capture/encoder classes,
proper state/resolution transitions, explicit synchronization/lifetime audit,
separate cursor handling and real Moonlight A/B measurements. Probe input is
only the primary plane; capture of overlays and nontrivial transforms is not
implemented here. Do not replace the standard capture path with this probe.

Existing CSC parameter temporarily enabled with independent five-minute rollback;
restored N after successful test, timer stopped, compiler container removed.
Kiosk image/config and start timestamp remained unchanged. GitHub comparison
run36339240710 completed successfully during this work; it predates this probe
and does NOT include a new Sunshine DMA-BUF capture implementation.
