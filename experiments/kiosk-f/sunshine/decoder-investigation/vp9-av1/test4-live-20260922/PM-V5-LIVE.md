# Hantro PM v5 live candidate: failure, 2026-09-22

Candidate signed module SHA256:
12f1208b47388a6d57cd2d3c56037fb61f926e5545f0fdd89bb59c3f468c55f8
Stored separately /config/kiosk-test/kernel-test4/pm-v5-live-1305/hantro-vpu.ko.
No installed module replaced. Same test4 kernel/VSI IOMMU, exact same mask0
setting which previously passed three decode/remove cycles with old module.
Blocked other Hantro cores using temporary driver_override. External fsynced
kernel logger on ThinkPad. Independent12minute cleanup timer checks mask0 and
runtime suspended before unloading; cannot recover a kernel/SoC hard hang.

Results:
1. Preflight/insmod succeeded; AV1 video3/media1 appeared.
2. 300frame NV12 output exactly matched previous software-verified baseline.
3. After2seconds, runtime_status=suspended; SSH command returned exit0.
4. Started follow-up SSH command to check suspended, mark REMOVE_BEGIN, unload,
   wait8seconds, reload and decode twice. SSH later timed out. External journal
   ends at HASH_DONE, before any REMOVE_BEGIN or driver-remove marker.
5. Ping2/2lost, SSH No route to host, ARP FAILED; NUC still reachable.

Therefore exact failing instruction is UNPROVEN: could be idle/power transition
between commands or entry into follow-up removal. Do not claim modprobe-r
returned or even entered driver remove. It is a post-decode loss of reachability
with v5+mask0, whereas baseline mask0 repeatedly survived. v5 is not accepted.
User asked to powercycle into unchanged normal-kernel default. Transient test
and cleanup units do not rerun after reboot. Waiting for recovery; no new ROCK
tests launched. On recovery retrieve remote hash-1.json/journal and verify boot,
kiosk/touch reconciler before further testing.

Source review before run: v5 moves enable/disable into runtime callbacks but
retains clock unprepare before runtime-PM shutdown in remove. Tested after
reported suspended state to avoid known active-clock teardown hazard. This
was insufficient to demonstrate stability; removal/power ordering still needs
instrumentation rather than declaring v5 a fix. No persistent workaround added.
