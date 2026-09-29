# Combined decoder patches and browser capture slots, 2026-09-22

Scope: RK3588 Test3 VP9 backend, RCB resizing fix, H264 B1 reference-list
memcmp length correction, HEVC SPS/RPS bounds validation, plus opt-in live
V4L2 MMAP capture-slot adapter (+2). Patches, provenance and module hashes
are in ../vp9-rcb-b1-rps-20260922. EBUSY retained. Does not include AV1 test4,
full multicore, NV15 browser import, or compiled Chromium pool patch.

The browser adapter is the same isolated capture-count-v3.so experiment as
../../h264-reorder/capture-buffer-experiment, mounted only into disposable
sandboxed Chromium153/Weston16 containers. Never a production LD_PRELOAD.
VP9 harness is copied from capture-count/tools-v3-both and only codecs=(vp9)
is changed; existing VP9 long-fixtures supply the matching HTML/video.

Procedure: pause D HDMI capture, load combined shared V4L2/H264/rkvdec modules,
run nine TRY_EXT_CTRLS boundary cases, three H264 and three HEVC decoded
reference comparisons, compare all300 VP9 decoded frame hashes. Then run
1080p60/30s browser fixtures in order baseline, +2, +2 (all three codecs).
H264/HEVC and VP9 fixtures are not identical content; compare settings within
each codec, not absolute inter-codec encoding efficiency. Baseline/+2 changes
only pool budget within these browser runs, all combined modules stay loaded.

Cleanup trap restores original installed modules and restarts D if previously
active. F kiosk remains active. No persistent kernel files, image defaults,
release workflows, or AV1 build sources modified.

## Limits

Short isolated functional/presentation tests, not a production release gate.
No physical HDMI presentation/latency validation, no 10-bit browser validation,
no in-band resolution-change test. Chromium source integration still requires
its own compiled validation, especially low-delay exclusion for D. No new
D default or universally increased buffer count is justified. Decoder hash
checks and HTML presentation counters are distinct; dropped frames are not
network packet loss. Correctness of every arbitrary video is not established.

## Results

All nine browser runs ended with1800 frames and V4L2VideoDecoder/platform=true.
All nine bounds cases passed; decoded H264/HEVC references passed three times
per codec; VP9 all300 frame hashes matched software reference.

| Codec | Baseline drops | +2 first | +2 repeat | Actual slots baseline/+2 |
|---|---:|---:|---:|---:|
| H264 B-pyramid |284|6|3|6/8|
| HEVC |4|3|2|8/10|
| VP9 Profile0 |2|29|3|10/12|

H264 capture-pool improvement survives combined kernel patches. HEVC and VP9
already have low baseline drops; no reliable extra-pool benefit demonstrated.
VP9's29-drop run did not repeat, so neither a systematic regression nor an
improvement is established. Do not globally increase slots across codecs.
Prioritize a bounded opt-in for the affected H264 non-low-delay MMAP path;
retain low-delay exclusion and verify the compiled implementation separately.
Both D and F services active after automatic original-module restoration.
