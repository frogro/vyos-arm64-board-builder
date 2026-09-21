# Instrumented Chromium build preparation

Status2026-09-21, 20:10 local: source and isolated ARM64 build dependencies ready.
GN generation is running with one thread after an earlier 3 GiB OOM.
NO compiled browser binary or deployment yet.

Exact source: chromium153.0.8010.47-2~deb13u1, matching live Debian package.
https://deb.debian.org/debian-security/pool/updates/main/c/chromium/
Included DSC records source archive filenames and SHA256. All three archives
were checked against it. Retrieved over HTTPS; local dpkg-source could not
verify DSC OpenPGP signature because uploader key was absent. Extraction
completed and Debian patches applied. This is not a signature-verification claim.

Local working tree outside git:
/mnt/entwicklung/projekte/VyOS/arm/vyos-arm64-board-builder/tmp/chromium153-instrumented/source
(~6.9GiB extracted; ~936MiB source archives).

Applied h264-reorder/buffer-lifetime/chromium-lifetime-instrumentation.patch
and the disabled-by-default capture-buffer-experiment feature patch. Source-context application passed against actual Debian tree.
The experimental SPS/RPS patch is deliberately NOT combined in the first
lifetime measurement: changing decode controls would confound the comparison.
Separate build variant required after instrumentation establishes a baseline.

Verified Debian rules for ARM64: use_v4l2_codec=true, use_vaapi=true,
use_av1_hw_decoder=true. Thus AV1 software result is not explained by blindly
assuming AV1 was compiled out; current driver advertises no AV1 decode format.
Build requires Clang22 and Debian Rust toolchain, with ThinLTO default on64bit.
The current ThinkPad has7.1GiB total RAM and only~3.5GiB available duringwork;
no unbounded compilation was launched. User extended the window to21:00 local.

Next build must preserve ARM64 V4L2 and normal sandbox, use bounded jobs/link
concurrency and memory, and account for ThinLTO memory before launch. Prefer
an isolated ARM64 build environment; x86 native compilation is not the target.
Do not claim a cross-build merely by overriding host_cpu in Debianrules.
No main/release workflow changes needed for this experimental build.

After successful compilation, replace the browser only in a disposable image.
Use h264-reorder/buffer-lifetime/trace-browser-instrumented.py (retains new
VyarmV4L2 events) with the matching harness. Repeat pyramid/no-pyramid with
reversed order, combine with kernel buffer trace, verify actual V4L2decoder,
then inspect free-buffer flags, pause events and reuse callbacks. Maintain
existing fallback and keep production D/F unchanged.

## Bounded local build attempt

A dedicated Docker daemon avoids the original daemon's unrelated missing-layer
problem. It does not repair or modify the original Docker storage. Socket
`unix:///run/vyarm-chromium-docker.sock`, service `vyarm-chromium-docker`, VFS data
under the sibling `tmp/chromium153-instrumented/docker/data`.

ARM64 Debian trixie runs through QEMU binfmt on the ThinkPad. Exact Debian build
dependencies installed successfully. `bootstrap.sh` shows the source configuration;
ThinLTO disabled, ninja/link concurrency one, 2 CPU quota, 3 GiB memory limit
(4 GiB including swap). Initial GN default parallelism hit the cgroup OOM limit.
Dependencies were retained in `vyarm-chromium-builddeps:20260921`; retry uses
`gn gen out/Release --threads=1`, then targets only the two modified C++ objects.
Object compilation would be a build check, not a complete browser or live proof.
All source/cache is outside the Git worktree. No release workflow modified.

## End-of-window outcome

Single-thread GN generation succeeded. Debian compiler exports were restored
after a manual retry omitted them. Native GN/Ninja orchestration reduced QEMU
overhead; actual Clang 22 still runs ARM64 under QEMU. The two object targets
require 3898 dependency steps. Direct object attempts remain blocked by real
generated Perfetto headers; the next header target alone has 426 steps.
No modified C++ object or complete browser build succeeded in this window.
The opt-in allocation guard is therefore not compile- or live-validated.
Build source, dependencies and cache retained outside Git for a later builder.
