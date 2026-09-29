# Profile D CPU conversion investigation, 2026-09-28

Live image: 999.202609250800-adf-20260928, kernel 6.18.50-vyos.
Kiosk remained active; no persistent config or binaries changed. RGA CSC
remained N. All test processes bounded by timeout and exited. Zero failed
units afterwards. HDMI capture was discovered as video0 (not yesterday's
video5); detected 1920x1080/60 timings synchronized before capture.

GStreamer 1.22.0 videoconvert defaults to n-threads=1. Eight CPU cores
available. Same BGR1080p to NV12 conversion, 120 frames per measurement:

| Input/path | Threads | Pipeline seconds | Approx frames/sec |
| --- | ---: | ---: | ---: |
| Synthetic black BGR in normal memory | 1 | 1.442 | 83 |
| Synthetic black BGR in normal memory | 4 | 0.550 | 218 |
| Synthetic black BGR in normal memory | 8 | 0.904 | 133 |
| HDMI BGR to NV12 | 1 | 12.381 | 9.7 |
| HDMI BGR to NV12 | 4 | 6.129 | 19.6 |
| HDMI BGR to NV12 | 8 | 6.307 | 19.0 |
| HDMI, pipe copy, rawvideoparse, NV12 | 1 | 9.697 | 12.4 |
| HDMI, pipe copy, rawvideoparse, NV12 | 4 | 7.738 | 15.5 |
| HDMI, NV12, mpph264enc, h264parse | 4 | 5.975 | 20.1 |

One short measurement each, including pipeline startup; these are throughput
probes, not end-to-end streaming latency or statistical performance claims.
Synthetic content differs from real HDMI; it isolates the memory/conversion
path but does not alone prove a specific cache attribute.

Capture without reading/converting pixels completed 120 frames in 2.112s.
HDMI capture currently enumerates only BGR3. userptr failed negotiation;
no working userptr path established. MPP test used process-local
VYARM_MPP_COLORIMETRY=1, bps=8000000, gop=60. No external service exposed.

## Conclusions and candidates

- Four conversion threads improve the actual CPU fallback about twofold,
  but do not make 1080p60 feasible. Eight threads did not improve real input.
- Large real-vs-synthetic gap and low-cost capture-only path point to CPU
  access of capture memory as an important bottleneck. Cacheability is a
  hypothesis pending driver/allocation instrumentation.
- Pipe copy is a diagnostic, not a proposed production implementation:
  extra copies/system calls cost too much and it drops original buffer
  metadata. A single in-process copy into cached memory remains untested.
- Next targeted experiment: owned cached staging buffer preserving caps,
  timestamps and color metadata; compare against direct four-thread path.
  Any DMA-BUF mapping must retain required CPU/device synchronization.
- RGA with the corrected CSC remains the previously demonstrated 60fps
  alternative. No RGA performance or color correctness retest claimed here.
- Do not silently lower color quality, bypass synchronization, or globally
  enable experimental CSC as a CPU optimization.

No code change added to the already running Actions 36381181401. A generic
bounded/configurable CPU thread option needs separate integration and
regression checks before changing defaults on other boards.

Evidence: /tmp/vyarm-cpu-convert-20260928/*.log on ROCK; combined local log
under work/cpu-convert-20260928 in the task workspace.

Primary references:
- https://gstreamer.freedesktop.org/documentation/videoconvertscale/videoconvertscale.html
- https://gstreamer.freedesktop.org/documentation/additional/design/dmabuf.html
- https://gstreamer.freedesktop.org/documentation/video4linux2/v4l2src.html
- https://cdn.kernel.org/doc/html/latest/driver-api/dma-buf.html

## Follow-up: in-process cached staging works

Bounded ctypes/GStreamer-API proof (no new runtime packages, no installed
library changes): appsink holds the V4L2 sample; allocate a new default
GstBuffer; map original READ and destination WRITE; one libc memcpy; unmap;
copy flags/timestamps/meta; pass unchanged caps to appsrc. Preserve ownership
until copy completion. appsink/appsrc queues bounded to two BGR frames.
This is a diagnostic harness for this exact linear BGR1080p layout, not a
production generic buffer transformer.

120 input AND output buffers verified via sink handoff count:
- Direct reference through the same appsink/appsrc harness, 4 threads:
  3.415s /35.14fps. The harness changes scheduling and pool pressure; this is
  the appropriate matched control and must not be conflated with the earlier
  single gst-launch pipeline's 20fps.
- Cached copy, 1 thread: 2.124s /56.49fps.
- Cached copy, 4 threads: 2.122s /56.55fps.
- Cached copy, 4 threads plus MPP H264: 2.130s /56.34fps.
- 600-frame encoded follow-up: all600 input and output buffers,10.137s,
  59.19fps including startup. Sum of copy/map/allocation times3.542s,
  overlapped with downstream work. This is not a CPU-utilization measurement.

Ten independently captured input frames were each fed through direct
single-thread conversion and cached-copy/four-thread conversion. The two
NV12 outputs compared SHA256-identical for every frame; copied BGR bytes
also compared equal. This proves no pixel change in these samples, not a
complete color-standard acceptance across all formats/ranges.

No RGA/CSC used, CSC still N. Kiosk and input helper active afterward. No
native D service or permanent CLI changes. Encoded output was counted at
h264parse/fakesink, not streamed to a remote client in this test. End-to-end
latency, longer runs, signal changes and generic strides/metas still require
integration testing. Proof scripts retained in cpu-conversion-proof/.

### Targeted upstream search

1. **Concrete GStreamer copy optimization:**
   fe61bc3cee1bc7b99b550005f77d8ece3649b4ec, MR7694,
   `video-format: reduce the number of memcpy if possible`.
   gst_video_frame_copy_plane uses one whole-plane memcpy when strides match,
   instead of copying each row. Listed in1.26 performance changes. Relevant
   when implementing staging via GstVideoFrame; our diagnostic already uses
   one bulk memcpy. It does not itself insert a cached staging buffer.
   https://github.com/GStreamer/gstreamer/commit/fe61bc3cee1bc7b99b550005f77d8ece3649b4ec
   https://gstreamer.freedesktop.org/releases/1.26/
2. **Concrete DMA mapping optimization:**
   726b2603b8c936298bb2a2ad37237259cf483233, MR10153,
   `v4l2allocator: Add KEEP_MAPPED flag to the allocated buffers`.
   Adds GST_FD_MEMORY_FLAG_KEEP_MAPPED to exported DMA-BUF allocations.
   Avoids repeated mappings; does not change CPU cache attributes. It targets
   that allocator path, so applicability to current MMAP capture is limited.
   https://github.com/GStreamer/gstreamer/commit/726b2603b8c936298bb2a2ad37237259cf483233
3. **Linux-media discussion:** Tomasz Figa,2023-07-05, explains coherent
   mappings are often uncached/write-combined on non-coherent platforms and
   why userspace must opt into V4L2_MEMORY_FLAG_NON_COHERENT. This is a
   driver/allocation candidate, not a ready GStreamer fix. Audited current
   main gstv4l2allocator.c REQBUFS call sites: no NON_COHERENT flag request.
   Do not enable cache skipping or change coherence without driver support.
   https://lkml.rescloud.iu.edu/hypermail/linux/kernel/2307.0/03460.html
4. **Radxa forum reproducer:** Rock3A low GStreamer performance discussion
   attributes decoder-buffer CPU access to uncached MPP memory and suggests
   RGA-assisted copy. Different device/source, corroborative only; not proof
   of our exact HDMI allocation. No reviewed drop-in patch extracted.
   https://forum.radxa.com/t/rock-3a-extremely-low-performance-in-gstreamer/12813

Recommendation: integrate a separately selectable generic cached-copy CPU
fallback, preserving format/stride/color/timing information, and retain the
existing validated RGA route. Do not replace all of GStreamer merely on the
assumption a newer version fixes this allocation boundary. No upstream patch
was installed, and Actions36381181401 does not include this new experiment.

## Native helper and image integration

Added cached-launch.c as an optional image input. Native launcher uses a pad
probe to allocate owned default memory, map/copy pixels, preserve timestamps,
flags and VideoMeta strides/offsets, then send the buffer through a bounded
2-frame queue to videoconvert (4 threads). The queue is necessary: initial
single-thread pipeline scheduling delivered about48fps through RTSP; queue
separation restored about60fps (600 decoded frames in roughly10seconds).
Native VyOS D configuration used gstreamer + colorimetry negotiated, HDMI
1080p60 and loopback-only MediaMTX. FFmpeg decoded600frames successfully.
The native helper produced identical active NV12 pixels to stock conversion
for a padded65x63 BGR test; unused output padding bytes differ as expected.

Selection is opt-in via existing `video colorimetry negotiated`: only packed
BGR/RGB CPU fallback uses staging when the helper is installed. Legacy,
RGA, other formats and images without the optional binary retain prior
behavior. CI builds the helper, checks it executes inside the target rootfs,
and verifies its bytes in both image/ISO squashfs. No global GStreamer
library replacement. CLI source-recipe pin updated for the reviewed runner.
Live test configuration and original runner restored after the test; helper
removed. No save, main merge or active D service left behind.

## Isolated upstream patch-behavior tests

No system libraries replaced. Per-process LD_PRELOAD shims reproduce the
reviewed diffs on installed GStreamer1.22.0. Copy-plane function extracted
from1.22 source with fe61bc3 equal-stride branch applied; allocator shim adds
KEEP_MAPPED at the fd allocator boundary used by this isolated DMA-BUF
pipeline. These are behavioral probes, not complete rebuilt upstream plugins.

120-frame DMA-BUF BGR1080p capture -> four-thread videoconvert -> NV12:
- baseline5.96s;
- copy-plane patch6.04s, instrumented copy-plane calls ZERO: not on hot path;
- KEEP_MAPPED6.03s, fd allocation calls2: no meaningful improvement.

A forced400-copy BGR1080p microbenchmark exercised the copy-plane function:
stock0.209857s, patched0.201843s, bytes identical. Single measurements; the
small difference is not a statistically established gain. Our staging helper
already uses a single bulk memcpy and does not call this copy-plane function.

First allocator probe shim failed symbol resolution for the dynamically
loaded allocator and crashed only its disposable gst-launch process. Timeout
terminated it. Replaced RTLD_NEXT lookup with explicit allocator-library
lookup and null checking; corrected probe completed. This was a harness
failure, not evidence of an upstream patch or kernel crash.

Native helper termination via SIGTERM succeeded within the2-second timeout
(timeout reports124 as expected). Invalid pipeline exits2 with an explicit
error. Kiosk active, no failed units, no gst-launch test processes left,
CSC N and unsaved configuration false after cleanup.

### CLI and fallback boundary

Current image is a TEST candidate. Existing negotiated color policy selects
cached staging only when conversion resolves to CPU and helper is installed.
This preserves legacy and RGA routes but couples color and allocation policy.
Before general release, prefer a separately reviewed generic CLI selector
(e.g. auto/direct/cached); these names are proposals, not available commands.

Current fallback is a startup decision. A runtime RGA failure does not
transparently rebuild the pipeline on CPU. A cached helper allocation/map
error fails rather than silently continuing with damaged output; service
restart is not equivalent to an automatic direct-CPU downgrade. Runtime
recovery, bounded retry policy and fault injection remain separate work.
No unproven upstream patch is added to Actions36382869073.

## Additional test build: independent selection and bounded recovery

Two additive native CLI nodes (GStreamer only):

```
set service kvm-over-ip video cpu-conversion cached
set service kvm-over-ip video conversion-fallback enabled
```

`cpu-conversion direct|cached|auto` defaults to `direct`. Cached staging applies
when CPU conversion of BGR3/RGB3 is selected; it does not displace a selected RGA
path. `auto` uses the helper if available; explicit `cached` requires its
installation. Colorimetry remains an independent setting. The fallback defaults
to disabled, preserving established behavior.

Enabled recovery first restarts a failed/stalled capture with CPU conversion,
then with direct CPU conversion, and stops retrying after those failures until
source change or service restart. A missing RTSP transport does not consume this
budget. Recovery is process-local and never rewrites saved configuration.
Allocation/layout/mapping failure in cached staging can also switch to direct
buffers within that process. Direct CPU fallback may reduce frame rate.

Validation: cross-compilation with -Wall -Wextra -Werror; KVM CLI/config tests,
supervisor recovery/exhaustion/source-change/transport tests, 106 kiosk tests,
profile and boot regression tests. On the ROCK, a process-local allocation fault
injection tested 30 synthetic 64x64 BGR frames: enabled recovery completed all
184320 NV12 bytes, identical to control; disabled recovery exited 1. No global
libraries or installed services were changed. Full installed native CLI and
end-to-end HDMI recovery remain checks for the resulting image; this isolated
fault test is not proof of recovery from every hardware hang.

The upstream GStreamer copy/mapping patches remain excluded. This additional
build retains the previous cached-copy run 36382869073 for comparison.
