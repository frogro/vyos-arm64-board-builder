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
