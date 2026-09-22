# Unified Chromium candidate, 2026-09-22

Experimental build started on the NUC; no finished browser or new live browser
validation yet. Standard D/F containers and release workflows are unchanged.
The former ARM64/QEMU compiler build and its watchdog are stopped. Its source
and partial objects are retained. The new output directory is independent.

## Included browser changes

Base: Debian Chromium 153.0.8010.47-2~deb13u1, source archive checksums in
`../chromium-instrumented-build/source.dsc` (the uploader signature was not
verified locally).

1. `../h264-reorder/buffer-lifetime/chromium-lifetime-instrumentation.patch`.
2. `../h264-reorder/capture-buffer-experiment/0001-opt-in-extra-capture-buffers.patch`.
3. All three NV15 patches pinned in `../hevc-main10/upstream-provenance.json`:
   Chromium formats, ANGLE, and EGL import capability gate. The ANGLE patch is
   applied inside third_party/angle. Include the Chromium 153 adaptation
   `../hevc-main10/chromium153-rejected-hunk-followup.patch`; retain P210/P410.
4. `../chromium-rps/0001-chromium153-hevc-sps-rps.patch`: optional controls are
   queried by capability, not board name. Parser/conversion ASan/UBSan harness
   passed again against the merged candidate; this is not a complete browser test.
5. `0001-restrict-capture-reserve-to-h264.patch`: extra capture buffers only for
   H264, stateless requests, MMAP, non-low-delay, bounded by VIDEO_MAX_FRAME.
   Feature remains opt-in, default extra count two; no blanket HEVC/VP9 increase.

`source-files.sha256` pins all 40 affected browser source files plus the cross-build helper after merging. The NUC
copy passes these hashes. AV1 and V4L2 are enabled; HEVC parser/hardware decoder
and HEVC platform support are explicitly enabled. VA-API and X11/Wayland support
remain present. Sandbox is not disabled by these build scripts.

The native Rust helper build exposed a Debian pre-generation metadata mismatch
(`default_for_rust_host_build_tools` vs `host_for_rust_host_build_tools`).
`0002-regenerate-native-rust-bindings.patch` bypasses only that native helper
pre-generation cache. Native bindings/Rust compilation now passes this point.
This does not change the browser's runtime decoder code.

## Performance and reproducibility

NUC source: `/home/photobooth/vyarm-chromium-build/source-cross`.
Dedicated Docker socket: `unix:///run/vyarm-nuc-docker.sock`.
Container: `vyarm-chromium-unified-build`.
Image: `vyarm-chromium-cross-builddeps:20260922`.

Clang22, Rust, GN and Ninja are native **x86-64** binaries; Clang produces actual
AArch64 objects (verified using ELF headers). Debian's cross-build integration
still uses QEMU for generated ARM64 helper programs, not for the compiler itself.
Rust proc macros use the native host toolchain and its default C++ library.
Do not install both architectures of libc++22: their Debian shared paths conflict.
Target libc++22 remains ARM64.

Eight compile jobs, all 16 logical CPUs available, 26 GiB memory / 30 GiB including
swap, one linker. ThinLTO and symbols disabled, optimized release build, PGO off.
These are build-cost tradeoffs, not a claim of identical runtime performance to
Debian's ThinLTO browser. Only chrome and chrome_sandbox targets are built.
No `-march=native` or ROCK board-name dependency. The build has no network access.

The dependencies were prepared in native Debian trixie with ARM64 multiarch and
`apt-get build-dep -a arm64 -P cross`. Setup requires working DNS (`--network host`
was used only during dependency setup). In a temporary copy of debian/control,
mark golang, generate-ninja, ninja-build and gperf `:native`; golang:arm64 otherwise
has unsatisfiable cross dependencies. Save the installed package manifest and
GN arguments with the artifact. See vyarm-cross.mk and vyarm-cross-build.sh.

## Overnight watcher

`watch-unified.sh` runs as NUC user unit
`vyarm-chromium-unified-nightwatch.service`. Logs/status live in the parent build
directory. Checks every minute; after verified memory exhaustion it retries
incrementally at four, then two jobs. Stops below 5 GiB free space without deleting
files. Unknown compiler failures stop for analysis, rather than blind restarts.
User lingering was enabled on the NUC so the watcher survives logout. The unit
uses `sg docker` because the existing user systemd manager lacked that group.
This is a local watchdog, not an autonomous code-fixing agent or Codex wakeup.
No Codex automation tool was available in the session.

## Kernel and integration follow-up (not browser patches)

The combined test module set contains VP9 VDPU381 support, RCB resizing,
H264 B1 reference-list comparison correction, and HEVC SPS/RPS bounds; retain
EBUSY protection. The separate AV1/IOMMU test4 build has not yet incorporated
all those combined fixes. Merge and validate them before claiming one complete
kernel candidate. GStreamer 1.28.7 tests establish independent decoder behavior;
GStreamer is not Chromium's decoder backend. Mesa/ANGLE, device permissions,
render groups, compositor/seat and matched UAPI remain necessary (see
`../main10-physical-20260922/DEPENDENCIES.md`). Sunshine MPP/RGA encoding is separate.

After build success: disposable browser image, sandbox-on H264 pyramid/no-pyramid,
HEVC ordinary and SPS/RPS/LTR, VP9 profiles 0/2 and HEVC Main10; compare decoded
frames and physical 1080p60 output, repeated starts/seeks and kernel logs. AV1
requires working driver/DT/IOMMU, not just this browser build flag. Preserve
production fallback until these pass.

Then provide a checksummed browser artifact for the optional D/F builder path.
VyOS Rolling continues to choose the kernel; do not pin an old kernel as a fix.
When compatibility fails, diagnose kernel/UAPI, browser and runtime independently;
rebuild Chromium on NUC if required and update the isolated builder integration.

## Start validation

Native compiler, GN, Ninja and Rust architecture verified; AArch64 object output
verified. A small C++ program also linked against the target libc++ using lld and
ran successfully through the cross-exe wrapper. Generated ARM64 browser objects
and native Rust helper compilation are progressing; more than 1,200 new build
steps completed within minutes, compared with the stopped compiler-emulated
attempt's roughly 1,000 steps in three hours. This is not a completion estimate:
steps vary substantially in cost and final browser linking remains untested.
