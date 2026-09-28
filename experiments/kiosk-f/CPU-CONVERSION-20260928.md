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
