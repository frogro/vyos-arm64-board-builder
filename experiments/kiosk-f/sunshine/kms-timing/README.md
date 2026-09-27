# Opt-in Sunshine KMS stage timing

Diagnostic patch for source 63d35f702ee9e362e43263742981836ec0710384.
Set SUNSHINE_VYARM_KMS_TIMING=1 for the Sunshine process. Without the variable,
clock reads and aggregate logging are skipped. One record per 60 successful
RAM-capture snapshots reports refresh, EGL import, prepare (including free image
wait), texture readback, cursor and total milliseconds. Failed snapshots and
post-return object cleanup are not included. Readback time can include GPU waits
and conversion; it does not identify a pure memory-copy cost by itself.

Containerfile reconstructs the existing pinned MPP/HEVC/RGA candidate, adding
this diagnostic only. It expects the historical sunshine-source.tar.gz archive,
the existing MPP, HEVC cleanup and RGA patches, plus rga-converter.hpp in its build
context. Do not interpret the OFF Vulkan switch as a tested Vulkan path.

Build context and log now reside at:
/mnt/entwicklung/build-environments/nuc-20260927/sunshine-kms-timing/
Local systemd unit: vyarm-sunshine-kms-local-20260927.service.
The initial native ROCK build was stopped at the user's request. Build now runs
on ThinkPad under arm64 QEMU with data on entwicklung, CPU quota 200%, memory 4 GiB.

Status at preparation: patch dry-run passed, compilation started; no stage timing
results yet. Use the same binary across the control and cached-mapping kernels.
Keep the live candidate bounded by an independent rollback timer and restore the
Kiosk configuration and Sunshine identity afterwards.
