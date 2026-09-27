# Optional direct GPU / RGA Sunshine capture

Experimental opt-in for the existing KMS RAM capture backend:

```
SUNSHINE_VYARM_DIRECT_RGA=1
```

Unset or any value other than `1` preserves the old capture path. This is separate
from `SUNSHINE_VYARM_RGA_TEST`, which accelerates color conversion only after RGB
readback. Do not assume enabling that older variable enables direct capture.

Data flow: Sunshine's selected KMS DMA-BUF (including AFBC modifier) -> separate
GLES context -> RGA-exported linear RGB target -> V4L2 RGA NV12 -> owned Sunshine
image -> existing software-frame / MPP encoder interface. NV12 is copied to CPU
memory; this is not an end-to-end zero-copy encoder. No per-frame full RGB
readback or upload. Cursor pixels are small premultiplied BGRA uploads, composed
on the GPU before conversion. The existing KMS source selection and implicit
producer DMA-BUF synchronization remain in use; no second DRM display discovery.

Requirements / limits:
- Linux DRM RAM capture, hardware GLES renderer and compatible RGA M2M driver.
- Corrected RGA color handling explicitly enabled at
  `/sys/module/rockchip_rga/parameters/experimental_full_csc`; this program checks
  the setting, never writes it. The kernel keeps its own revision gate.
- SDR 8-bit BT601/BT709, limited/full range, even dimensions <=4096 per axis.
- Single-plane XR24 input; other formats, HDR/deep color use the old path.
- RGA owns allocation so its DMA addressability requirements are respected.
- NV12 matrix/range metadata travels with each image and is reset on fallback.
- Scaling/padding stays in the existing encoder conversion path.
- Shared image slots retain RGB allocation capacity for same-frame fallback.
- GPU completion precedes RGA queueing; borrowed source fd/import lives through
  completion; both V4L2 queues stop before buffers/imports are destroyed.
- RGA wait deadline200ms. Failure releases state and disables direct capture
  until the display capture object is initialized again. Standard capture then
  handles the same frame; no repeated failing allocation loop.
- Missing/inaccessible RGA devices or disabled CSC do not modify the host.

This does not add capture of extra overlay planes or stronger producer-buffer
locking than upstream KMS. Do not infer complete cursor/rotation/tearing quality
from FPS or numerical color tests alone. Multiple clients with different color
spaces still require qualification beyond the single-stream test target.

## Reproducible build

Start from the context documented in ../kms-timing/README.md. Replace its
Containerfile with this directory's Containerfile and add these three files:
`0001-direct-gpu-rga-capture.patch`, `direct-rga.cpp`, `direct-rga.hpp`.
All existing MPP/HEVC cleanup, RGA converter and timing patches remain included.
The direct patch applies after the timing patch. The extra build dependencies
are libegl-dev and libgles-dev; links EGL/GLESv2. No Chromium rebuild is needed.

`test-direct.cpp` validates the actual new helper, not the older feasibility
probe: eight color/range/geometry cases, dynamic source updates, an opaque cursor,
unsupported-format rejection and recovery, reused context with format changes.

```
g++ -std=c++17 -O2 -Wall -Wextra -Werror \
  direct-rga.cpp test-direct.cpp -lEGL -lGLESv2 -o test-direct
```

Run only in an isolated device-enabled container with an independent restoration
of the prior CSC setting. The live image and its Sunshine state need not change.

Build/test results and streaming acceptance are tracked separately; numerical
helper success alone does not establish improved Moonlight latency.
