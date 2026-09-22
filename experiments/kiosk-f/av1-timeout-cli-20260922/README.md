# Bounded AV1 recovery and generic media CLI, 2026-09-22

User authorizes one hour starting17:25CEST, through18:25. No main/release workflow
change, no push, no modem changes. Original browser/container configuration kept.

## Kernel candidates

Isolated external module, signed with the existing trusted key (not in artifacts).
Base is test4 plus the previously tested powered-core-pulse diagnostic. Two
reproducible preparation scripts and incremental patches are retained.

- Reset helper attempts all selected reset lines, retaining the first error.
- Powered pulse propagates a failing PM put; validation precedes variant init.
- Failed clock enable drops the acquired PM reference; failed codec preparation
  cancels its watchdog, releases clocks/PM and completes the job once.
- AV1 prepare_error previously called hantro_irq_done and returned an error to
  device_run, which also completed the job. Remove the duplicate AV1 completion
  when pairing with the central cleanup fix. Do not apply only half this pair.
- Diagnostic one-shot lost-completion injection acknowledges the hardware IRQ but
  withholds the job completion; the existing2s watchdog exercises powered reset.
- A separate one-shot preparation error exercises the pre-hardware unwind path.

Three withheld-completion tests on original test4 passed with three subsequent
300-frame bitexact decodes and removal. Three preparation-error tests on the
combined VSI identity/TLB candidate passed, again with300 exact frames each.
See live-results-final and final validation.json for remaining runs.

These are controlled software fault injections, NOT naturally wedged hardware.
No PMU bus-idle handshake is implemented; no generic production AV1 timeout
callback is promoted. IOMMU hard-IRQ PM handling still requires a dedicated audit.
The experimental powered reset is enabled explicitly, never by normal CLI.

Two harness preflight failures occurred before decoder use: missing ephemeral
watchdog helper after reboot, then unloaded v4l2_jpeg dependency for insmod.
Both logs retained; prerequisites fixed. They are not decoder regressions.

## Browser/CLI and an unresolved restart

The first CLI auto test on old test4 completed AV1 Main10:1800frames,22drops,
V4L2VideoDecoder. During the following software comparison the ROCK became
unreachable and returned on the normal kernel. No panic/pstore evidence survived.
Do not claim the cause or assert that the IOMMU changes alone fixed it.

After a one-shot boot of the existing combined IOMMU candidate, repeating the
comparison with the second module completed: auto1800/11(V4L2), software1800/50
(Dav1d), no-decoder auto1800/59(Dav1d), then successful module removal. All three
reach EOS. Presentation drops are not network loss and these short runs are not
statistical performance benchmarks. Runtime device probe and reserve opt-in are
provided by the actual new CLI policy helper, not hardcoded by the harness.

Generic CLI: auto/software; separate opt-in H264/AV1 reserves; read-only media
startup status; native image-label compatibility checks before commit; binary
hash and accessible device/graphics checks inside container. No hardware-required
promise, no false claim from device presence. Per-video evidence is external CDP;
status explicitly reports unknown actual decoder. See ../CLI.md.

68 unit tests plus3 host-fix regression tests and upstream config/op XML/template validation passed. Runtime
companion image built separately; original running image was not replaced.
New package build uses an isolated source tree and distinct artifact version.
No browser compilation was necessary. Full image/physical-display integration
and strict hardware-only enforcement remain outside this tested scope.

Final combined timeout check also passes: one injected missed completion with the
single-completion error fix and both VSI switches, then300 bitexact frames and
module removal. Total7 injected error cycles,2100 exact subsequent frames.
No physical monitor assessment was requested in this hour. Restored original
running test4 kernel (candidate parameters absent), normal boot default unchanged,
next_entry empty; only original kiosk container runs, D video/input services active,
watchdog inactive, no failed units at final check. Prior logrotate collision was
not changed or declared permanently fixed. Wi-Fi returned to homebase.

## Additional boot/display finding — do not hide in decoder success

Complete combined-boot kernel log shows fdd97e00.iommu page faults and a
`drm_atomic_helper_wait_for_vblanks` warning at17:49:30, before the17:51 AV1
preparation-error tests. Device-tree source identifies fdd97e00 as vop_mmu
(display), separate from fdca0000 VSI AV1 IOMMU. Logging overflow and MMC interrupt
latency accompanied the burst. This is NOT a clean whole-system kernel run even
though subsequent decoder tests passed. No proven causal connection to earlier
browser-comparison reboot or the VSI patch. Final restored test4 boot does not
show these messages. Next bounded investigation: display/framebuffer transition
and mapping lifetime during boot; keep AV1 decoder results separate. No extra
kernel patch or broad stress run was started for this finding in this hour.

## Native package build at end of one-hour budget

Full ARM64/QEMU vyos-1x package build deliberately stopped at18:20 CEST during
upstream pylint, before the18:25 user deadline. No completed .deb or live native
upgrade is claimed. The68 focused tests,3 host regressions, XML checks, generated
configuration templates and reference cache passed; full package checks remain
incomplete. Build dependencies are cached in the dedicated local Docker image
`vyos-profile-build:media-cli-deps-20260922`; source and a non-started resume script
are preserved. See package-build-status.json for exact provenance and paths.
The original ROCK kiosk/package remain active.
