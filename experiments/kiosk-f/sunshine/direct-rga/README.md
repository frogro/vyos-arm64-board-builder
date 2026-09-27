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


## Experimental upright capture

`SUNSHINE_VYARM_KMS_ROTATION=90|180|270` rotates the GPU copy clockwise,
including the cursor, before RGA conversion. Default is 0. This is an explicit
capture correction, not a universal mapping from a compositor's rotation label.
Only the SDR direct-RGA full-output path supports it. Unsupported setup is
rejected; a mid-stream direct-path failure ends rotated capture rather than
silently falling back to an unrotated/cropped image. Pixel and logical input
extents use the rotated geometry. Validate absolute pointer mapping live.

The numeric helper tests all three rotations, both landscape/portrait source
sizes, BT.601/709 and limited/full ranges. Comparison includes cursor and an
asymmetric top marker. See rotation-reference-20260927.txt. A matching pixel
reference does not establish physical-monitor or remote-input acceptance.


`SUNSHINE_VYARM_ABS_ROTATION=90|180|270` separately corrects Sunshine's
absolute virtual-mouse coordinates on Linux. It does not alter physical touch
or relative-mouse packets. Both flags are off by default. For opt-in direct RGA
under Wayland, kiosk-sunshine derives them from existing KIOSK_ROTATION: capture
uses the inverse quarter-turn and absolute input uses the configured turn.
X11 and non-direct paths retain their environment unchanged. CLI acceptance gate
is still retained pending complete rebuilt-runtime integration.

### Portrait live acceptance, 2026-09-27

Initial GPU 90-degree correction produced an upside-down picture (user report).
GPU 270 degrees produced upright portrait but wrong absolute mouse directions.
GPU 270 + absolute input 90 then passed the user's direction and click-position
test at 1080x1920 H.264/60 on the ROCK, whose local kiosk rotation is 90.

Final client statistics: rendering 59.97 FPS, incoming 60.76 FPS; host processing
mean 12.9 ms, min/max 9.8/123.8 ms; network frame loss 0%, jitter loss 0.98%,
LAN RTT 1 ms. This is a short live test, not a sustained-latency qualification.
HEVC portrait and physical local rotations 180/270 are not live-qualified by it.
The helper's 24 rotated color/geometry cases matched the reference at sampled
pixels exactly; original color cases remained within 1 level. Invalid 45-degree
rotation is rejected and subsequent valid capture succeeds.

Test binary SHA256:
`dc7acada7dc2c9d744767b97e840d46eb7843358dd85617c915e8868148b0b01`.
Patch application is staged in both direct build Containerfile and CI context
assembly. Default capture remains unchanged. No kernel/Chromium rebuild needed.
Runtime supervisor rotation derivation passed unit tests; this live test used
explicit flags in an isolated server and the ownership-checked input bridge.
Thus the permanent, same-container policy path and next image still need
integration acceptance; this is not a claim that main/released images include it.

The normal kiosk and CSC=N were restored after testing; temporary input cgroup
rule and rollback timer removed. Prior Sunshine binary is preserved separately.
