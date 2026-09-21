# HEVC follow-up on unchanged live test3, 2026-09-21

Isolated Chromium153/Weston16 headless GPU compositor, sandbox retained. Production
kiosk unchanged. Existing v3 capture ioctl adapter: baseline vs +2 capture slots.
The source Chromium patch compiling on NUC is NOT tested by this adapter.

## Cases

- Existing 30-second 1080p60 Main8 HEVC fixture, packet-copy loop to120seconds:
  four7200-frame runs, extra-buffer order0/2/2/0. Exact existing H264 long-test
  harness/HTML reused, codec changed toHEVC. Each browser process/container fresh.
- Additional synthetic10-second1080p60 Main8 fixtures: ref6/B4/pyramid and
  ref1/noB, each compared0/2/2/0. Both use libx265 ultrafast,8Mbps target,
  BT709 limited; metadata and hashes in fixtures.json. Confirmed high-ref SPS
  max_dec_pic_buffering_minus1=6 and max_num_reorder_pics=2; noB has has_b_frames=0.
  These are distinct encoder settings, not matched-content/performance claims
  against earlier H264 fixtures.
- Resource cap1GiB per disposable browser/compositor container, network-none.
  Tests serialized. Fixture encoding took place on ThinkPad, not during ROCK
  playback. /dev/video2 confirmed rkvdec and /dev/media0 retained from working
  test harness; these diagnostic paths must not become production constants.

Raw results and test scripts on ROCK:
`/config/kiosk-test/kernel-test3/hevc-followup-20260921/`.
Long runner unit vyarm-hevc-followup-20260921 (900s bound); short runner waits
for it and runs under vyarm-hevc-short-followup-20260921 (1200s bound).
collect.py exports reduced measurements without screenshots/full CDP event dumps.

## Interpretation boundaries

HTML drops are presentation drops, not RTP/network packet loss or a pixel test.
Final-frame hashes compare buffer variants only; they do not prove all decoded
frames or correct colors. Existing BT709-vs-REC601 browser import issue remains.
These synthetic clips do not replace HEVC SPS-RPS/LTR conformance tests: existing
rps-conformance-test3 documents mismatches and missing-control kernel warnings.
Seek/pause and source reload were already tested for HEVC (capture-buffer-experiment
followup-results.json); changing sources is not in-band resolution renegotiation.
Remaining: in-band resolution changes, injected allocation/driver failures,
longer soak, physical display validation, SPS/RPS patched browser, Main10 NV15
browser output after NUC build. Do not call HEVC fully qualified.


## Completed results

All12 runs ended with V4L2VideoDecoder/platform=true and expected frame counts.

| Case | Baseline drops | +2 drops | Actual capture buffers |
|---|---|---|---|
| Main8 120s /7200frames |70,75|80,52|8 vs10|
| ref6/B4 10s /600frames |5,5|3,4|18 vs20|
| noB 10s /600frames |2,2|4,4|8 vs10|

No consistent HEVC benefit comparable to the problematic H264 small-pool fixture.
High-reference input already gets a substantially larger baseline pool. Keep
extra slots experimental/disabled by default; do not promote for all HEVC.
Each group's four final-frame PNG hashes match. That is consistency evidence,
not decoded-all-frames or color correctness. Total28,800 long-run plus4,800
short-run frames observed. All readouts and per-run thermal samples are in
results.json. No kernel/module/browser/production settings changed.
