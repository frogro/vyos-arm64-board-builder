# VP9 original submission and Collabora refs

Found original four-part series, 2026-07-26, author Venkata Atchuta
Bheemeswara Sarma Darbha, copied to linux-media and Collabora maintainers:
https://lists.openwall.net/linux-kernel/2026/07/26/761
Message-ID: 20260726-b4-add-rkvdec2-vp9-vdpu381-v1-0-180fb2d1f10c@gmail.com
Base: 1229e2e57a5c2980ccd457b9b53ea0eed5a22ab3.

1. Rename shared reference-buffer helper.
2. Extract shared VP9 functions.
3. Add VDPU381 backend (Profile0/2).
4. Align decoded bytesperline to 64 bytes.

This original submission is the preferred review baseline before adapting the
community snapshot. It already credits segmentation-map size and altref scale
fixes plus the stride correction. The reported score is 224/305 on three
boards. Known failures include small dimensions, inter-frame resizing and
remaining unexplained vectors. Submission is not proof of merge or correctness
on our ROCK. No newer revision was confirmed in this search.

Important corrected attribution:
https://lists.openwall.net/linux-kernel/2026/07/17/1866
The author explicitly retracts the earlier claim that PM teardown ordering
fixes green VP9 inter frames. It fixes a clock reference leak. The reported
picture recovery came from Alex Bee's reset-controls change with Randy Li's
PMU idle export. Evaluate/reset-test these independently; do not conflate with
our Hantro AV1 BIU reset issue or treat the PM reorder as the VP9 picture fix.

Collabora refs verified through git ls-remote (web endpoint blocked):
https://gitlab.collabora.com/hardware-enablement/rockchip-3588/linux.git

- rockchip-devel: ebc9042dde3f832fbe2c1f28347420a876197831
- rockchip-v7.0: f442588d0176b5fc04fa03a9415d0a8f00daf4a6
- rockchip-v7.1: 566f27ab33057295aa5d4e2d6cedcbfa50a5dcd2
- rockchip-v7.2: 7c94261a67f7cbf1127e48bf3d2c2467e8b7a9de

Ref presence alone does not establish VP9 inclusion. Source-level comparison
of those pinned tips remains pending. Partial raw mail downloads are retained
outside Git in tmp/vp9-mail-series; not yet a complete apply-tested series.
The current AV1 build and production files remain unchanged.
