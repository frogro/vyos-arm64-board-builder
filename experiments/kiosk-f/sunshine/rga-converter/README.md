# Experimental Sunshine V4L2 RGA conversion

Opt-in test path, not a release default. Requires the independently tested
RGA2E FULL_CSC module from rga-investigation on the current ROCK.

The C++ helper discovers rockchip-rga by sysfs name and validates V4L2 mem2mem,
streaming, requested BGR0/NV12 formats, dimensions, color space and range. It
keeps one mmap buffer per queue across frames, handles row padding and explicit
BT.601/709 full/limited conversion, bounds wait time to approximately 100ms,
and closes a failed device. No board name or hardcoded video node is used.

The Sunshine patch is guarded by SUNSHINE_VYARM_RGA_TEST=1 on Linux. It only
accepts same-size BGR0 -> NV12; scaling and unsupported combinations retain
swscale. This is a copy-based path, not zero-copy. A passing color test alone
is not a speed improvement over swscale or an end-to-end latency result.

Standalone probe built with g++ -std=c++17 -O2 -Wall -Wextra -Werror on ROCK
in the pinned builder and run with the signed experimental module. 120 frames
for each of eight geometry/matrix/range cases (960 total), with padded CPU
input/output strides, passed at max sample error1. Mean times 4.18–4.60ms
include copies and sample validation. Raw measurements: results-20260921.txt.
The previous Python portrait check needed even-aligned interleaved UV sampling
and a range-aware reference; the corrected probe passed all four cases.
Original kernel module was restored after every probe, kiosk remained active.

Build recipe uses exact local cleanup builder
bd1c0b9333c6cd76338b6396feb2dbb5d0f202fe4e595d7e32912d16cdb762d7
and runtime
3fac48e2a9b718d0347acfa997196486963df120546a8339c4b0017fd42b6005.
These are local reproducible test dependencies, not published release artifacts.
Actual Sunshine compilation and paired streaming validation are pending.
Also pending: same-object geometry changes, injected timeout/error recovery,
comparative CPU/latency measurements, complete metadata negotiation review.
