# AV1 removal/reset investigation, 2026-09-22 afternoon

User authorizes autonomous investigation until 17:00 Europe/Berlin. Branch-only
experiment; no installed modules, boot default, normal profile or release workflow
changed. This is a candidate and diagnosis, not a production reset fix.

## New source findings

1. Rockchip vendor `develop-6.1` at77168c8d5ab82399f65a80e9f807b50ba37cf483:
   `drivers/video/rockchip/mpp/mpp_av1dec.c:av1dec_reset` requests PMU bus idle,
   asserts the two core resets, waits5us, deasserts both, releases idle.
   Its rk3588s.dtsi requests SRST_A_AV1/SRST_P_AV1 only, not the two BIU resets.
   Our Hantro removal leaves selected lines asserted after clock unprepare and
   runtime-PM disable. Same physical IP, different driver/lifetime contract.
   Source: https://github.com/rockchip-linux/kernel/blob/77168c8d5ab82399f65a80e9f807b50ba37cf483/drivers/video/rockchip/mpp/mpp_av1dec.c

2. Mainline VSI driver atf0100363d8c374bd8e9ea7c9ba02744f0b802ca4 differs materially
   from our Armbian6.18 backport: enable-state tracking, non-synchronous runtime-PM
   get in TLB flushing, map/unmap flushes rather than exported per-frame helper.
   Blind replacement would break our Hantro vsi_iommu_restore_ctx dependency and
   newer attach_dev callback ABI. Full paired backport needs separate validation.
   Our old flush_tlb_all calls pm_runtime_resume_and_get while holding the domain
   spinlock with IRQs disabled. This is a concrete sleeping/locking audit target,
   not evidence that this path caused the observed remove hang.
   Source: https://github.com/torvalds/linux/blob/f0100363d8c374bd8e9ea7c9ba02744f0b802ca4/drivers/iommu/vsi-iommu.c

3. Old driver's runtime resume converts every non-NULL iommu->domain to the
   enclosing vsi_iommu_domain and locks its lock. The identity domain is instead
   a standalone struct iommu_domain, so that conversion is invalid if identity
   has been attached. `vsi-identity-resume-guard-candidate.patch` excludes that
   case and compiles as an isolated object against test4. NOT live-installed;
   not proven reached during our normal Hantro module removal. Provider is built
   into Image, so this requires a separate testkernel. Newer source also needs
   careful identity-domain review, not an assumption that newer equals fixed.

4. PM-v5 remains rejected: previous live failure happened after successful
   decoding and before a logged remove entry. It was tested upstream on G1;
   it is not a verified AV1 unload fix. Do not combine it with this experiment.
   https://lkml.iu.edu/hypermail/linux/kernel/2607.3/09663.html

5. Other RK3588 reports use VSI IOMMU to address CMA exhaustion, e.g.
   https://github.com/dongioia/rock5bplus-rkvdec2/tree/2c67fd3a3fde501d3f90082ad7f1c849d4f2d6cc
   and the vendor MPP forward-port reference
   https://github.com/yisding/rock-5b-ysp/tree/main/kernel-drivers/patches/forward-port-rk3588
   These provide comparisons, not a tested fix for our Hantro remove scenario.
   Our test already has VSI_IOMMU=y and CmaTotal=0; merely enlarging CMA does not
   explain/fix the reset-dependent failure. No verified matching published fix
   was found in the additional GitHub/mailing-list searches.

## New live evidence

A trace-instance-only diagnostic with the original module and mask0 completed
300 bit-exact frames and removal. After REMOVE_BEGIN the PM core resumes BOTH
AV1 and IOMMU. After REMOVE_DONE the provider suspends about96ms later. Thus
checking suspended before modprobe-r does not guarantee no later provider MMIO.
This supports, but does not prove, the held-reset/provider-access hypothesis.
See trace.txt and pm-state.txt; tracing instance removed afterward.

## Powered core-pulse candidate

`hantro-powered-core-pulse-diagnostic.patch` adds a default-off diagnostic:
`vyarm_test_av1_remove_pulse=1` requires the validated AV1 split-reset resources
and mask3. After userspace/media teardown, before clock/PM teardown:
- runtime resume/get, retaining supplier via the existing device link;
- enable prepared Hantro clocks;
- assert only core resets0/1, wait5us, deassert them even after partial failure;
- disable own clock reference, drop runtime-PM reference;
- omit the later permanent reset assertion.

This is our diagnostic adaptation inspired by vendor sequencing, NOT a copied
upstream fix. It does not implement vendor PMU idle handshake (API absent from
our mainline-derived kernel). It leaves BIU lines unchanged. Error recovery,
clock/PM teardown failure handling and reset ownership still require review.
No change to frame decode code, no PM-v5 clock rewrite, no IOMMU replacement.
Signed external module SHA256:
5046eb52a2818f924efed93cfa2749ba1617fdf6fddb990a4875f75cca625e0d
Source/output kept separately under builder tmp/av1-reset-research-20260922.
Original source/kbuild/module installation untouched; signing key not copied.

## Guards and test record

Independent8minute reboot timer plus temporary DesignWare hardware watchdog.
Watchdog open/keepalive/magic-close activation/deactivation verified; driver
rounds30seconds to44seconds. Expiry-reset itself was NOT deliberately exercised.
This improves fallback but is not proof every SoC/bus hang can recover. Normal
GRUB default unchanged, next_entry empty. Watchdog restored inactive after tests.
https://docs.kernel.org/watchdog/watchdog-api.html

- First insmod attempt lacked v4l2_jpeg dependency and did not load the module;
  retained failure transcript. Dependency explicitly loaded for subsequent runs.
- First actual pulse trial:300/300 frames exact, removal and idle successful.
- Five subsequent load/decode/idle/remove cycles: each300/300 bit-exact,
  both reset operations return0 each time, no lost reachability.
- Browser AV1 Main10/P010:1800 frames,43 presentation drops with PM event trace;
  hardware V4L2VideoDecoder confirmed, EOS. Not a physical HDR/10-bit panel test.
- Forced SIGKILL of a separate active GStreamer client: exit137; subsequent
  fresh300-frame decode bit-exact; pulse removal successful.
- Attempt to disable tracing completely caused trace_marker EBADF before
  module load. Excluded; corrected control disables events but keeps markers.
- Browser control without PM events:1800 frames,31 drops, EOS and removal pass.
  Compared with earlier6drops, this is variable presentation performance, not
  evidence of decoder corruption. Background profileD encoding and substantial
  rsyslog activity are present; no controlled causal performance conclusion.
- Three long-idle cycles: each300/300 bit-exact; after removal and60seconds,
  AV1 power domain off-0, ACLK/PCLK enable counts0; next load/decode works.
- Concurrent hardware H.264:7200 frames over120seconds, zero sink drops, while
  three AV1 load/decode300frames/pulse/remove cycles succeed. See
  pulse-coexistence3/neighbor.json and corresponding trace/kernel log.
  Earlier harness attempts lacked PythonGI and then qtdemux; neither reached
  an AV1 module load. They are retained and excluded from decoder results.
- Total:14 successful candidate module removals (1+5+1+1+3+3). Baseline mask0
  trace is separate. Every candidate assertion/deassertion returned0.

No malformed-bitstream/forced decoder-timeout recovery claim: AV1 codec_ops
currently has no reset callback; clean/client-abort removal and watchdog job
recovery are distinct paths. Do not advertise full recovery on these results.

## Next integration gates

Prefer a variant capability/callback for hardware-specific removal sequencing,
not a ROCK board-name check or a user-facing CLI reset knob. Preserve other
Hantro variants' defaults. Only the RK3588 AV1 revision is exercised here.
Before normal-image integration: settle PMU idle/reset ownership, balance/report
all PM/clock error paths, test decoder timeout separately, repeat boot/shutdown
and system-suspend cases, and pair any VSI update with its Hantro consumer.
Identity-domain guard is separate, compile-only and needs a testkernel.

## Additional source audit (not live-tested)

`vsi-nonsleeping-tlb-candidate.patch` replaces synchronous runtime resume under
irqsave/domain spinlock with get-if-active. An enable-time TLB flush is added
for invalidations skipped while suspended. It compiles as an isolated object
against test4; it is our candidate, not an upstream cherry-pick. Ordering and
concurrency still require a testkernel and decode/reference verification.

The original hard IRQ handler also calls pm_runtime_resume_and_get. Evaluate
active-only access versus a threaded IRQ with correct shared-IRQ ownership and
acknowledgement; no IRQ patch is claimed here. Test4 lacks PROVE_LOCKING and
DEBUG_ATOMIC_SLEEP, so quiet logs cannot exclude those bugs.

Pulse error-path audit: the existing split-reset helper returns on first error,
so a deassert failure can prevent attempting the second line. The successful
runs all returned0, but the comment that both lines are always attempted is too
strong. A production helper must attempt release independently for every line,
report the first error, and account for pm_runtime_put_sync_suspend failures
(currently ignored). Probe validation placement must also preserve clock unwind.
These limitations are recorded without silently changing the tested binary.

Source drivers/base/dd.c __device_release_driver explains why the pre-remove
suspended state was insufficient: driver core resumes the device for removal.
PMU bus-idle ownership and provider access after remove remain integration gates.

## Final state

At16:29 CEST: same test4 kernel, normal boot default unchanged, next_entry empty.
No Hantro diagnostic module loaded; all video-codec driver_override values null;
no tracing instances or active vyarm-av1 units; hardware watchdog inactive;
no failed systemd units. Original kiosk-test container remains running. This
turn does not assert physical touch quality or install any production reset fix.
