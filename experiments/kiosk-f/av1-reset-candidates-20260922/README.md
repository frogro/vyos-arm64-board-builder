# AV1 IOMMU candidate live validation, 2026-09-22

Authorized window:16:32–17:32 CEST. Diagnostic only, no production defaults.

## Already known boot-setup error repeated

The panic=30/kexec issue in this run was already diagnosed at11:36:52 in the
[test4 report](../sunshine/decoder-investigation/vp9-av1/test4-live-20260922/README.md).
Reintroducing it was a repeated test-setup mistake. Follow the central
[boot checklist](../BOOT-TEST-CHECKLIST.md) before subsequent boot experiments.

## Build and isolation

Cloned test4 kbuild; private mount namespace presents the clone at its original
path and substitutes only drivers/iommu/vsi-iommu.c. This preserves incremental
command reuse without modifying the baseline source/build. Built Image only,
same kernelrelease and ABI, existing signed modules/initrd/DTB reused. Build
completed with memory limit3GiB, -j1, CPUquota90%. Image hash recorded separately.

Two default-off, writable diagnostic switches allow isolated A/B runs with no
AV1 clients bound: vsi_iommu.vyarm_identity_guard and vyarm_nonsleeping_tlb.
They are not supported user CLI settings. Instrumentation logs which paths run.

One-shot GRUB entry vyarm-av1-candidates uses separate vmlinuz-f-av1-candidates;
normal default untouched, hantro blacklisted. A12minute boot timer
returns an unconfirmed startup to normal after systemd starts. Early boot hangs
before systemd may still require a power cycle. Each live decoder experiment
additionally uses the already-validated temporary hardware watchdog and timer.

## Planned coverage

- Both switches off: control decode/powered-reset removal.
- Identity guard only: decode repetitions; unbound AV1 group DMA→identity,
  runtime suspend/resume→DMA, three repetitions. Require guard-hit evidence.
- TLB candidate only: decode repetitions; helper invokes flush_iotlb_all on the
  unbound AV1 DMA domain while provider suspended and active. Require logging
  ret0/ret1, and successful subsequent decode/reference hashes.
- Both on: regression repetitions and browser Main10 if time permits.
- Restore normal boot and verify original services before conclusion.

The explicit flush helper is hardware-specific test code, not a generic driver.
It refuses a bound device or non-DMA domain and only invokes the existing IOMMU
API. Test controller serializes domain changes. No faults are injected into
other devices or active production workloads.

## Status

16:39 first one-shot reboot requested. Candidate reached SSH and kiosk; then
VyOS system_option.py removed the unmanaged panic=30 cmdline option and issued
kexec to /boot/vmlinuz. This produced normal6.18.50-vyos with the old BOOT_IMAGE
label retained, so /proc/cmdline alone cannot identify the actual running image.
No candidate switch had been activated. See first-boot-kexec.txt and captured
system_option source. This is not evidence of a candidate decoder crash.

16:49 removed panic=30 from the separate entry, unloaded the preloaded kexec
image, requested a second one-shot boot. Set kernel.panic at runtime only after
VyOS startup is complete; verify uname AND candidate sysfs parameters before
experiments. ThinkPad briefly tested saved VyOS-AP connection under120second
rollback timer; returned to homebase automatically. ROCK AP gateway is10.3.141.50.
Live validation still pending.


## Results available at16:58 CEST

Second boot stable with test4 release and both candidate sysfs parameters.
VyOS router, kiosk and input service active. Boot guard stopped after verification;
runtime kernel.panic=30 set only after config load. No production config change.

- Switches N/N: one300-frame exact-reference decode and powered-pulse removal.
- Identity Y/TLB N: three300-frame exact-reference decodes/removals.
- Identity-domain probe: three DMA→identity→suspend→resume→DMA cycles pass.
  Six VYARM_IDENTITY guard hits recorded (explicit resume and return to DMA).
  Decoder was unbound, group6 contained only AV1; original DMA mode restored.
- Identity N/TLB Y direct probe: three suspended and three active flush calls.
  Logs prove ret0 skipped suspended MMIO, enable-time invalidation, ret1 active
  invalidation; all callbacks return. Provider remains suspended after skip.
- Identity N/TLB Y: three further300-frame exact-reference decodes/removals,
  after explicit domain and cache tests.

All reset cycles use the previously validated powered pulse. These results do
not show that either IOMMU patch alone cures permanent-reset hangs, nor that
hardware timeout recovery works. The intentionally unsafe identity case with
guard disabled was not exercised. Cache callback completion is not exhaustive
proof of every concurrent page-table remapping scenario.


17:04 follow-up: both switches enabled passes three further exact300-frame
cycles. Chromium AV1 Main10/P010 V4L2 decode reaches EOS with1800frames and8
presentation drops. This is not a controlled performance comparison against
previous runs and not a physical HDR/display validation.
Concurrent hardware H264 reaches7200frames over120.045s with zero sink drops
while three AV1 exact300-frame load/reset/remove cycles complete.


## Consolidated candidate results

| Switches / scenario | Evidence | Result |
| --- | --- | --- |
| Both off |1 decode/reset cycle,300 frames | Exact reference |
| Identity only |3 cycles,900 frames | Exact reference |
| Identity domain transitions |3 transitions,6 guard-hit logs | Resume/return to DMA pass |
| TLB only |3 cycles,900 frames | Exact reference |
| Explicit TLB calls |3 suspended skips +3 active flushes | Both branches reached, return normally |
| Both enabled |3 cycles,900 frames | Exact reference |
| Chromium AV1 Main10 |1800 frames,8 presentation drops | V4L2 hardware, EOS, removal pass |
| Concurrent H264/AV1 |H2647200/0 drops; AV1 3×300 | Exact AV1 reference, all removals pass |
| SIGKILL client/reopen |Exit137; fresh300 frames | Exact reference, removal pass |

Total15 successful powered-pulse removals on candidate kernel;14 exact-reference
files of300frames each plus the browser run. No BUG/Oops/SError/call trace in
captured candidate kernel log. Results and branch coverage checked by
validation.json. No deliberate baseline memory corruption or decoder timeout.

The identity guard now has direct live branch coverage. The TLB candidate has
live active/suspended coverage plus subsequent decode, but concurrent mapping
stress and full lifecycle/error review remain required. Neither is a production
builder default yet. A full upstream VSI backport remains a separate paired
consumer/provider task; these focused tests do not validate that replacement.

17:06: switched both flags back off, verified no diagnostic modules and inactive
watchdog, disabled candidate boot timer. Original GRUB default compares bytewise
unchanged. Requested one-shot return to previous test4 with its confirmation
timer enabled. ThinkPad restored to homebase, Wi-Fi rollback timer stopped.
17:11 post-return verified: previous test4 kernel, candidate parameters absent,
normal GRUB default unchanged and next_entry empty. Kiosk, input reconciler and
profileD video service active; logrotate.service reports a state-lock collision,
no diagnostic modules, watchdog
inactive, AV1 group DMA, all decoder overrides null. Confirmation timer disabled
again. ThinkPad on original homebase. See final-health.txt.

The initial boot retry consumed time but did not exercise either candidate.
All live candidate results belong to the later stable boot ID stored in
 test-boot-id.txt. No main/release workflow, modem config or production defaults
changed. Candidate Image/menu and evidence retained for explicit future testing.


### Separate boot-service observation

The regular logrotate.service failed with exit3 because its state file was locked
by the rsyslog-triggered /usr/sbin/logrotate /etc/logrotate.d/vyos-rsyslog job.
A single normal service retry reproduced the same collision. No process was
killed, no lock bypassed, no configuration altered, and no failed state hidden.
The rsyslog-triggered rotation continues; the regular service remains failed.
This is an outstanding logging-service issue, not an observed decoder failure.
See logrotate-startup-collision.txt, logrotate-processes.txt, logrotate-result.txt.
