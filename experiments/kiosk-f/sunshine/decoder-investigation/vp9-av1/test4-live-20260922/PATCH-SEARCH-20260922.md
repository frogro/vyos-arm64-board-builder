# AV1 and related patch audit, 2026-09-22

Read supplied Collabora mainline-status PDF (4 pages, saved 2026-09-21),
rendered all pages and extracted embedded mailing-list URLs. Its AV1 row
separates basic decoder (6.7-rc1) from VSI IOMMU (7.2-rc1). Neither entry is
an end-to-end Chromium or module teardown guarantee.

## AV1 fixes already present in test4

Downloaded original patch mails; reverse dry-run against test4 source succeeds
for all hunks in each patch (offsets only). No source modified by this check.

- CDEF enable computation:
  https://lore.kernel.org/linux-rockchip/20251209103401.21943-1-benjamin.gaignard@collabora.com/
- Transform-mode mapping:
  https://lore.kernel.org/linux-rockchip/20251209103417.21966-1-benjamin.gaignard@collabora.com/
- Tile-info allocation size:
  https://lore.kernel.org/linux-rockchip/20260114090710.71473-1-benjamin.gaignard@collabora.com/

These are not missing fixes to add again. Test4 also already has VSI IOMMU.

## Hantro runtime PM candidate

Newer v5 found, downloaded and externally compiled; see PM-REVIEW.md and the
v5 candidate patches. No live deployment. This fixes clock/PM resource leaks
on job errors, not a demonstrated reset-after-remove defect. The author tested
G1 codecs, not AV1. No verified published fix for our exact mask3 + VSI IOMMU
removal hang was found in this search.
https://lkml.iu.edu/hypermail/linux/kernel/2607.3/09663.html

## Chromium capture reserve: analogy confirmed experimentally

H264 B1 reference-list comparison and RKVDEC RCB patches cannot simply repair
Hantro AV1: different backend, register files and codec reference handling.
The shared userspace capture-buffer reserve IS relevant. Tested isolated
Chromium153 with sandbox, Weston16 headless GL, V4L2VideoDecoder, NV12,
1080p60 AV1, 120s/7200frames, same source/flags and production kiosk running.
Existing capture-count-v3 interposer changes only positive MMAP capture
REQBUFS for the exact decoder node. Logs verify requested/returned counts.

| Configuration | Frames dropped | Percent | Cgroup CPU percent |
|---|---:|---:|---:|
| HW baseline 1, 10 buffers |831|11.54|60.00|
| HW baseline 2, 10 buffers |964|13.39|64.08|
| Software Dav1d control |176|2.44|170.26|
| HW +2, 12 buffers |52|0.72|64.62|
| HW interposer +0 control |881|12.24|66.33|
| HW +2 repeat |56|0.78|66.40|
| HW +4, 14 buffers |59|0.82|65.59|

All reached EOS. CPU covers browser/compositor container, not only decoder;
100% represents one CPU equivalent. Browser-reported drops are not network
packet loss. No physical-display quality claim. Synthetic single-fixture
results do not establish all-content/10-bit/4K conformance or endurance.
Three native GStreamer runs each decoded7200frames with0sinkdrops in35.31–36.67s.

Two extra buffers are the supported next experimental choice. Do NOT silently
apply globally or assume identical needs across codecs/boards. Current NUC
build's feature is intentionally H264-only; no active build source was changed.
AV1 opt-in extension and actual new-binary validation remain follow-up work.
The interposer result is not proof that the not-yet-built feature works.

Raw browser JSON is retained in tmp/av1-iommu-test4/live-extended-1229; reduced
results with raw SHA256 are in extended-results.json. Buffer harness copies
are retained here. Trace/frames omitted from compact summaries deliberately.

## GitHub / forum cross-check

https://github.com/dongioia/rock5bplus-rkvdec2
Reports RK3588 + VSI IOMMU + stock Chromium hardware playback. This is useful
corroboration of architecture, not verification of our kernel or teardown.
Forum companion indexed but full fetch failed; technical claims checked against
its author's repository instead:
https://forum.armbian.com/topic/61497-guide-system-wide-in-browser-hw-video-decode-on-rk3588-mainline-debian-13-trixie-—-and-the-4k30-cma-gotcha-nobody-warns-you-about/

VP9 concrete fixes:
https://github.com/warpme/minimyth2/issues/73
https://github.com/beryllium-org/linux-beryllium/pull/8
Altref vertical scale, larger segmap storage and capture bytesperline addressing.
Checked OUR separate tmp/vp9-rcb-b1-live-test3 VDPU381 backend: vscale assignment,
524288 segmap and bytesperline MV/reference pitches already present. Do not
mistake old rkvdec-vp9.c's 73728 constant for the separate VDPU381 backend.
These are VP9 safeguards, not an AV1 unload fix. Portrait/resize/10-bit broader
validation still needed before production acceptance.

Collabora's Chromium validation documents capture allocation/format diagnostics:
https://www.collabora.com/news-and-blog/news-and-events/chromium-hardware-codecs-on-mediatek-genio-700-and-720-from-test-plans-to-real%E2%80%91world-performance.html
Transfer the diagnostic methodology, not MediaTek-specific assumptions.

PDF pending Rockchip Power Domain series remains an explicit research gap:
https://lore.kernel.org/linux-rockchip/1789733258-10133-1-git-send-email-shawn.lin@rock-chips.com/
Lore raw returned403; Patchew mirror404, exact-ID search gave no match. Have not
read its diff; no claim it fixes our AV1 behavior. RCB/multicore and HEVC RPS PDF
links were already audited in ../vp9-rcb-b1-rps-20260922/README.md; distinct from
Chromium emitting missing SPS/RPS controls.

## End of this test batch

All test browser containers ended. Removed Hantro with diagnostic mask0 and
cleared temporary other-core driver_override values. Kiosk and input reconciler
active, no failed systemd services. Kernel still test4, next normal boot remains
original default. PM v5 candidate not installed. No release/main workflow edit.
