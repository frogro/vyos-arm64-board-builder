# Bounded transition test and configuration audit, 2026-09-22

User authorized18:36–18:56 CEST; subsequently requested comparison of concrete
settings first. New test sequence stopped on that steering. No production
browser/CLI changes or new kernel build.

## Software-only failure before any AV1 load

At18:38:05 start software browser on original test4, with hantro_vpu absent.
HTTP video request18:38:26, last stderr18:38:27; result JSON empty. External
dmesg stream contains start marker then SSH timeout, no fault trace. Next boot
returned normal kernel, verified18:41:34. Hardware watchdog and fallback had
been armed; exact reset cause is not recorded. Hardware AV1/transition phases
were never reached. Thus prior AV1 decode or loaded Hantro is not necessary
for this symptom. This still does not prove a graphics bug vs another system
failure. Reboot confirms interruption beyond a mere lost browser connection.

## Restore and interrupted old-flags control

Selected existing test4 once, checked actual boot entry has NO panic= argument,
normal default unchanged. Access via LAN delayed; AP at18:47 verified correct
kernel and all production services. Disabled boot confirmation timer.
Old-flags control began18:48:24. User requested differences-first; stopped
sequence, cleanup18:48:58, no result JSON. Do not count this as pass or failure.
No Hantro was loaded, watchdog inactive after cleanup. Final boot ID
4aff5400-c1f2-417c-8dec-eb12682a7cd8, test4 kernel, only original kiosk container,
router/kiosk/inputs/D-video active, no pending next_entry. Current dmesg has no
matching display faults. ThinkPad returned to homebase under temporary timer.

## Concrete differences from successful reference

Reference commit2d83c69, av1-main10-software.json:1800/46drops, EOS.
Same binary verified SHA256d1f979a39d0402060364e5a9202cb6e8772a7e3ec90c91622151defcb851eeb6.
Same Weston headless GL, Wayland, ANGLE GLES,1920x1080, memory1500m, shm256m,
sandbox and media fixture path. No evidence of a missed memory/sandbox option.

CLI probe added at a1e7e3c removes the entire prior enable-features list, then
replaces it with policy features. Reference NativePixmapAccurateYuvMatrix is
not present in the capability manifest. Auto keeps3base features and requested
AV1 reserve, dropping color opt-in and unrequested H264 reserve. Software
returns only disable-accelerated-video-decode and no base features. See exact
flags in settings-comparison.json and source diff. Decoder buffers apply to
hardware capture, not software decode; color import is a separate graphics
policy and should not silently disappear when switching decoder selection.
A controlled followup should preserve the verified rendering policy while
changing only decoder selection. Do not blindly force every hardware option
on all boards or declare omitted color opt-in the crash cause.

Counterexample: shorter CLI software flags already completed1800/50frames at
17:54 on the combined VSI candidate. That kernel differed from base test4.
The15:19 successful reference used base test4, so the combined VSI patch is
not established as required for software. Runtime/history, graphics lifecycle
and power remain unisolated. Existing VOP fault burst belongs to a separate
boot and not this failure. No physical output validation in this task.
