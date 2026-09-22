# AV1 removal follow-up, 2026-09-22

Test4 adds VSI IOMMU; mask 3 leaves both core reset lines asserted on removal.
The same mask passed three exact-decode/reload cycles on test3 without IOMMU.
Next single-variable control: mask 0, which leaves all four resets deasserted.
This is a diagnostic, not a production policy or generic hardware default.

Source review: remove currently unprepares clocks, disables autosuspend/runtime
PM, then asserts the selected resets. IOMMU runtime suspend writes its control
register before disabling its clocks. Shared power/reset ownership is suspect,
but exact failure is unproven. Do not infer it solely from proximity in time.

Separate upstream candidate: Tharit Tangkijwanichakul, PATCH v4, July 28 2026:
https://patchew.org/linux/20260728045921.4761-1-tharitt97@gmail.com/
Moves Hantro clock enable/disable into runtime PM callbacks and balances job
failure paths. Author tests ROCK5B Hantro G1 H264/MPEG2/VP8, not this AV1/IOMMU
remove scenario. Not evidence of an AV1 fix. Candidate is upstream-derived,
not an independently developed clock-management patch.

Local adaptation only preserves test4's three-argument
v4l2_m2m_buf_copy_metadata(src, dst, true). All seven hunks pass patch --dry-run
against a copied test4 hantro_drv.c. Not compiled or deployed; review remove
ordering and clock preparation lifetime before combining. No source kernel,
normal image recipe or release workflow changed.

## Newer v5 found in follow-up search

https://lkml.iu.edu/hypermail/linux/kernel/2607.3/09663.html
Message-ID: 20260729060440.2092-1-tharitt97@gmail.com
Retrieved series mbox via Patchew. v5 supersedes the v4 candidate: split clock/
error-path management and DEFINE_RUNTIME_DEV_PM_OPS cleanup into two patches.
Retained test4 metadata third argument; patch 2 first hunk used fuzz 1 at the
unchanged runtime-callback boundary, reviewed resulting source. External
module compiled successfully against test4 source/kbuild on 2026-09-22.
Stored separate tmp/av1-iommu-test4/pm-v5-candidate; no installed module changed.
NOT deployed or functionally tested. Author's G1 tests do not validate AV1.
Removal still unprepares clocks before disabling runtime PM; review that
lifetime together with IOMMU/reset ordering before treating v5 as an unload fix.
