# Afternoon continuation 2026-09-22

14:29 CEST: user extends autonomous test authorization to 17:30 Europe/Berlin.
USB-C to USB-A PD-injector HID test added; continue Main10/browser work.
No modem changes, no main/release workflow edits or push. Production kiosk
retained. Current running test4; normal boot default unchanged.

Main10 120s completed, 7200frames/83drops, V4L2 hardware, CPU69.2% oneCPU.
HID USB-A five captured runs pass including default OUT endpoint and three
software reenumerations. See hid-usba-20260922; supersedes universal endpoint
workaround requirement. No composite HID/storage claim.

Chromium final candidate includes AV1 opt-in and V4L2 low_delay forwarding;
both incremental NUC builds already finished. See chromium-nuc-live-20260922.
Currently checking whether per-poll full frame-list serialization affects
long browser measurements, then consolidate patches/evidence in local commit.

14:45 CEST update: six USB-A input runs total3000 press/release pairs, all exact,
including default endpoint and ~80s final run. Test gadget detached.
Main10 summary-only polling23/7200drops, CPU61.4%; H26418/7200drops.
CDP kPlay→kEnded120.11s H264,120.19s Main10; page elapsed includes startup.
H264 five resolution switches and eight seeks pass; Main10 eight seeks pass.
Range server/stale callback corrections recorded. H264 high-reference600/6EOS.
Final binary/source manifest saved and runtime backed up on development disk.

15:06 CEST: VP9 Profile2 browser decode passes, but RGB comparison exposed
legacy REC601 import for BT709. New opt-in color candidate compiled and HEVC
Main10 RGB error improves7.1→1.4; VP9 A/B in progress. AV1 10-bit exposed
missing P010 single-buffer layout, correction+test compiling incrementally.
No permanent driver replacement or production browser switch. USB tests done,
all test gadgets gone; Kiosk/input services retained.

15:19 CEST: P010 browser fix compiled, AV1 10-bit passes1800/6drops with
hardware confirmed; software46drops and~247%CPU vs hardware~64%. AV1 8bit
regression passes. Kernel driver safely unloaded; bootback timer canceled.
Color A/B VP9 also improves7.28→0.95RGB error. P010 unit-test suite building,
then final commit. BT709-full and BT601-preservation color regressions running.

15:29 CEST: V4L2UtilsTest rerun passes9/9, including P010. Three stale Linux
modifier expectations corrected in a separate test-only patch; initial failure
logs retained. Production services and original media modules restored; Hantro
unloaded, no pending experimental rollback/reboot timers.

16:30 CEST: new AV1 reset/remove experiment completed14 successful removals.
Powered five-microsecond core pulse (BIU unchanged) instead of held reset after
PM teardown; separate diagnostic module, default-off, vendor-inspired, not
production-ready. Three60s powered-off idle cycles and concurrent H2647200frames
zero sink drops pass. Browser Main10 and killed-client/reopen pass; variable
browser presentation drops remain documented. Original kiosk/input and D video
running, diagnostic module/watchdog/timers removed. No reboot this turn.
Two separate VSI identity-domain/TLB candidates compile only; no provider
replacement. Error paths/PMU idle/decoder timeout still need validation.
See av1-reset-research-20260922/README.md, validation.json and exact traces.

17:08 CEST: IOMMU candidates built into separate incremental Image with default-off
A/B switches. Identity guard directly exercised via three DMA→identity→resume→DMA
cycles, six guard hits. Active-only TLB path tested explicitly three times each
suspended/active, then decode. Fifteen total powered-pulse removals pass;14×300
frames bit-exact, Chromium Main10 hardware1800/8drops, concurrent H2647200/0drops,
SIGKILL client recovery exact. Captured kernel log has no BUG/Oops/SError.
First candidate boot was replaced by normal kernel because VyOS system_option.py
removed unmanaged panic=30 and kexec'd /boot/vmlinuz. Retried without that boot
argument, setting runtime panic only after config load. Do not trust BOOT_IMAGE
alone after kexec. Original test4 return in progress; candidates not defaults.
See av1-reset-candidates-20260922/README.md and validation.json.

17:11 CEST: returned to previous test4 kernel, candidate parameters absent;
Kiosk/input/D-video active; logrotate state-lock collision remains (regular retry reproduced exit3); watchdog inactive, no diagnostic
modules/overrides. Normal default unchanged, next_entry empty; boot timer disabled.
ThinkPad back on homebase. Candidate tests finished within the authorized hour.

User correction recorded: panic=30/kexec was already diagnosed in the11:36 test4
boot; the16:42 occurrence repeated a known setup error. Central mandatory
BOOT-TEST-CHECKLIST.md and profile README link now record the preflight rule,
runtime-only alternative, actual-kernel verification and limits of boot timers.
No live changes made for this documentation correction.

## 17:25–18:25 bounded recovery/CLI task

User authorized one hour, avoiding repeated broad tests, plus agreed media CLI.
Four controlled AV1 watchdog injections and three preparation-error injections
recover to2100 bitexact subsequent frames. Fixed duplicate AV1 prepare-error
completion and PM/clock unwind in isolated signed module; both VSI candidates
included in later tests. Not proof of arbitrary real hardware wedge recovery.
Initial browser auto succeeds; following software run interrupted by unexplained
reboot. Preserved as unresolved, not attributed to a driver without evidence.
Combined-candidate repeat passes auto/software/no-decoder browser paths. No more
decoder stress rounds. Generic F decoder CLI subset implemented and tested;
strict hardware-only and D encoder/remote conversion knobs remain unpromoted.
68 tests plus3 host regressions and upstream config/op schemas pass. Runtime
companion built separately. Native package building locally in dedicated Docker;
no Chromium rebuild needed. Original test4 running state and kiosk image restored,
D active, watchdog/timers disarmed, no failed units in final check. See
av1-timeout-cli-20260922/README.md and CLI.md for exact boundaries.

Final log audit found a separate combined-boot VOP display-IOMMU fault burst and
vblank timeout before AV1 tests. Not present in final restored test4 boot. Recorded
as an additional shipping blocker; do not describe the entire candidate kernel
as warning-free or infer that the AV1 VSI changes caused it.
