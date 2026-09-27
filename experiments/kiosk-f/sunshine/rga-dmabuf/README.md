# RGA DMA-BUF feasibility, 2026-09-27

Experimental standalone probe; no production setting or main change.

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

1. Restore/verify FULL_CSC behavior on the exact next kernel; repeat both probes.
2. Validate GPU import/render into an RGA-addressable linear exported buffer,
   with format/modifier support and fence/lifetime synchronization.
3. Feed RGA NV12 output to MPP with explicit colorspace/range and bounded queues.
4. Integrate opt-in Sunshine path with safe fallback, then measure real streaming.

Normal kiosk continued running unchanged. Test Sunshine and compiler containers
stopped; test binaries retained under /config/panthor-sunshine-20260927.
No images were rebuilt locally and no global Mesa/default capture changes made.
