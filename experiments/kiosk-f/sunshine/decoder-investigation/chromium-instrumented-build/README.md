# Instrumented Chromium build preparation

Status2026-09-21: complete matching source downloaded/extracted and lifetime
patch applied; NO compiler run, NO new browser binary or deployment yet.

Exact source: chromium153.0.8010.47-2~deb13u1, matching live Debian package.
https://deb.debian.org/debian-security/pool/updates/main/c/chromium/
Included DSC records source archive filenames and SHA256. All three archives
were checked against it. Retrieved over HTTPS; local dpkg-source could not
verify DSC OpenPGP signature because uploader key was absent. Extraction
completed and Debian patches applied. This is not a signature-verification claim.

Local working tree outside git:
/mnt/entwicklung/projekte/VyOS/arm/vyos-arm64-board-builder/tmp/chromium153-instrumented/source
(~6.9GiB extracted; ~936MiB source archives).

Applied only h264-reorder/buffer-lifetime/chromium-lifetime-instrumentation.patch
at this stage. Source-context application passed against actual Debian tree.
The experimental SPS/RPS patch is deliberately NOT combined in the first
lifetime measurement: changing decode controls would confound the comparison.
Separate build variant required after instrumentation establishes a baseline.

Verified Debian rules for ARM64: use_v4l2_codec=true, use_vaapi=true,
use_av1_hw_decoder=true. Thus AV1 software result is not explained by blindly
assuming AV1 was compiled out; current driver advertises no AV1 decode format.
Build requires Clang22 and Debian Rust toolchain, with ThinLTO default on64bit.
The current ThinkPad has7.1GiB total RAM and only~3.5GiB available duringwork;
no unbounded compilation was launched, and the authorized window ends19:30.

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
