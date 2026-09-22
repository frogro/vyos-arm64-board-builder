# AV1/IOMMU test4 live validation, 2026-09-22

Kernel: 6.18.50-vyos-f-test4-av1-iommu. Full build completed 10:42:43 CEST;
packaging completed 11:18:40 with exit 0 and all checksums passing. Earlier
packaging waiter timed out before build completion; restarting it completed.
Artifacts transferred to /config/kiosk-test/kernel-test4 and verified there.
Separate kernel, DTB and initrd; existing boot files untouched. GRUB next_entry
is consumed once; normal default unchanged. A conditional 15-minute boot timer
provides reboot fallback after systemd starts. Early firmware/kernel hangs
still require physical reset; no claim of autonomous recovery before systemd.

## First boot: test setup caused an extra reboot

The initial test menu added panic=30. VyOS system_option.py manages panic and,
on mismatch with persisted options during startup, loads /boot/vmlinuz and
/boot/initrd.img then requests systemctl kexec. The journal shows this orderly
kexec at 11:36:52; normal kernel 6.18.50-vyos was running by 11:38. The timer
service did not execute. This is not evidence of a power supply fault.
The user observed the second boot and eventual kiosk recovery; D/F services
were active and systemd had no failed services when inspected.

Removed panic=30 only from the experimental boot entry. An isolated execution
of the actual installed MANAGED_PARAMS, parser and generate_cmdline_for_kexec
verified old command line triggers kexec and corrected command line does not.
No production VyOS source/config was changed to suppress its safety handling.
The second one-shot boot was then requested. AV1 playback results pending.

The initramfs is about 557 MB because it includes all candidate modules and
available firmware. GRUB load was visibly slow; this is not the final release
packaging strategy. Temporary modprobe.blacklist=hantro_vpu avoids probing all
Hantro cores during boot; tests explicitly load AV1 after capability preflight.
The probe isolates other Hantro cores through temporary driver_override,
uses split reset mask=3, checks 300 NV12 frames against the existing software
reference, and repeats load/decode/unload with cleanup on exit. No new default
for another board or a release image follows from this experiment.

Second boot reached test4 successfully (2026-09-22 11:48 CEST), no failed
systemd units. Disabled the 15-minute boot fallback after healthy SSH/kiosk
verification. Normal GRUB default remains unchanged.

Touch initially absent: selected host evdev nodes were event2/3/6/7 while native
container targets remained event0/1/4/5. Xorg/libinput could not resolve the
corresponding host paths. The installed input reconciler service was inactive
and lacked a boot dependency. Running the existing reconciler refreshed runtime
Quadlet mappings and restarted only the kiosk. Xorg now lists ILITEK touch and
mouse plus Logitech inputs; touch enabled with the 90-degree transform.
Physical confirmation requested, still pending. Added the reconciler helper,
service and container Wants dependency to install-startup.py; enabled the same
Wants dependency live and started the installed service. Existing drop-in saved
as kernel-test4/kiosk-retry.before-touch.conf. Eleven startup/reconciliation tests
pass. AV1 read-only preflight passes: vsi_iommu bound, group 6, no decoder module
loaded; test4 decoding cycles remain pending.

## First decoding attempt, approximately 11:58 CEST

User confirmed recovered physical touch before proceeding. Repeated preflight
passed on test4; launched probe.sh as transient vyarm-test4-av1-cycles.service,
RuntimeMaxSec=360, output appended to /config/kiosk-test/kernel-test4/cycles.log.
Immediately following launch, SSH timed out repeatedly, ping had 100% loss and
ARP neighbor became FAILED while NUC remained reachable over the same LAN.
User answered "nein" to whether the kiosk still responded (interpreted as no
response; question wording also mentioned freezing). Suspected system hang,
not a successful AV1 validation. Exact stage (module probe, decode, or removal)
is UNKNOWN until persistent logs can be recovered. No additional tests started.
Requested physical power cycle into unchanged normal GRUB default. Transient
test service does not restart at boot. A systemd timeout cannot recover a fully
hung kernel; no claim of guaranteed automatic recovery. Existing one-shot boot
fallback had been disabled after healthy test4 boot verification.

NUC Chromium still advances: 52454/56256 around 11:59. A .exit file containing 1
is stale (03:39); live build log modification time and active nightwatch indicate
it is not the current build's result.

Recovery verified at 12:02 CEST: uname is 6.18.50-vyos (normal kernel), user
confirms touch works. cycles.log, decode-1.log and hardware-1.json exist but are
zero bytes; no reference-comparison result survived. Previous-boot journal lacks
test service entries and ends before the test; pstore is empty. Saved previous
journal on ROCK as kernel-test4/journal-after-hang.txt. Thus no exact failing
kernel operation can be established from preserved logs. A subsequent test must
stream logs off-host and split module attachment, first decode, and removal into
separate stages rather than rerun the same combined probe blindly.

## Staged attempt, 12:09–12:12 CEST

Rebooted one-shot test4 with normal default preserved and 15-minute boot
fallback enabled. Automatic kiosk reconciliation restarted the kiosk once and
restored touch (user confirmed); both kiosk services active.

Kernel log streamed over a separate SSH connection to ThinkPad with fsync per
line; AV1_CAPTURE_READY marker verified before loading. Staged outcomes:
- Module attach with remove mask 3 succeeded, exposing video3/media1.
- First-frame GStreamer hardware decode reached EOS and returned successfully.
- Complete 300-frame NV12 hardware output matched software hashes exactly.
- Separate modprobe -r returned (STAGE_REMOVE_RETURNED captured externally),
  then SSH stopped responding before the subsequent uptime check. Kernel
  stream ends at REMOVE_BEGIN; finer remove diagnostics did not arrive.

This strongly localizes the loss of reachability to removal or the immediately
following power transition, not this run's decoding. Exact reset/IOMMU operation
remains unproven. Do not claim stable AV1 reuse. Requested power cycle back to
normal kernel; no further decoder loads initiated. Files staged-*.log retain
external evidence, including the returned removal marker.

## Mask 0 control succeeds, 12:23–12:25 CEST

Fresh test4 one-shot boot, same binary, IOMMU, fixtures and userspace. Only module
parameter changed: remove_reset_mask=0 instead of 3, so removal does not assert
core or BIU reset lines. Three complete load/decode/remove cycles succeeded;
each 300-frame NV12 hash list exactly equals software reference. Eight-second
post-remove observation each time, SSH responsive, next load successful.
External logs and all hash arrays saved. No failed services, ACK failures,
Oops/SError or IOMMU faults observed. This implicates core resets in combination
with the test4 IOMMU path; it does not establish exact register-level cause or
a production-correct policy. No permanent reset omission integrated.

Cleanup: Hantro unloaded, temporary other-core driver overrides cleared, boot
fallback timer disabled, next_entry empty; normal GRUB default unchanged.
Current kernel remains test4, kiosk and input reconciler active. Next ordinary
boot selects normal kernel. No new kernel compile or normal workflow changes.

Follow-up: longer idle/reprobe, teardown with IOMMU runtime power held, reset
ownership/order review; separately evaluate upstream runtime-PM clock patch.
Do not combine both changes for the initial causal control.
