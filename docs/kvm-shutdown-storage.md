# KVM virtual-media shutdown investigation (19 September 2026)

ROCK 5B running 999.202609161112 reported two shutdown failures:
`/config: target is busy` and `/run/live/persistence: target is busy`.
A temporary runtime-only diagnostic unit captured process handles and mountinfo
after vyos-router stopped and before config.mount stopped. No userspace file
descriptor or working directory under /config was found. The kernel USB gadget
still had an Alpine ISO from /config/kvm-over-ip/media attached to its mass
storage LUN. The file-storage kernel worker holds this backing file outside
normal process FD inspection.

Live correction: vyos-kvm-gadget-cleanup.service is armed at startup and destroys
only the builder-owned vyos-kvm gadget on stop. Its ordering stops local input
first, then ejects virtual media and removes the gadget, before vyos-router,
config.mount and configfs are stopped. It does not alter saved KVM settings or
start a gadget. Images without KVM do not install the unit.

Comparison reboot: previous boot cc375a4c84634f6d96609257c9bb0129 showed successful
cleanup followed by `Unmounted config.mount.` The next boot automatically
reattached the configured ISO, and no failed service remained. This establishes
the virtual-media holder as the cause of the /config failure in this test.

The separate persistence unmount failure remains. Mountinfo shows the active
root overlay using persistence/boot/<version>/rw and work as upper/work dirs.
That backing filesystem cannot be detached while the root overlay still holds
it. This requires investigation of the native live-initramfs/final shutdown
handoff, not forced or lazy unmounting in the gadget cleanup unit. This test does
not establish a safe fix or prove the final backing filesystem unmount status.

Diagnostic unit and executable were under /run and vanished on reboot. The
captured report was retained on the diagnostic workstation; no monitoring
service remains. The corrective gadget cleanup unit remains enabled live and
is installed by the common finalizer only for future KVM-enabled images.

## Follow-up: native persistence teardown

Read-only inspection on 19 September found /run/initramfs empty: no executable
shutdown pivot environment is installed. The rebuilt initrd includes Debian
live-boot plus 9991-vyos.sh, but no shutdown handoff script. The current root is
an overlay whose upper/work directories reside on /dev/mmcblk1p3 mounted at
/run/live/persistence. This explains EBUSY during the ordinary mount-unit stop.

The live 9991-vyos.sh exactly matches upstream vyos/vyos-build commit
4571978c8542a1f996af8a4913c787eecfb0b15d (SHA256
1d8b0b7508703c571fcf6cfc1688a2793598f15547a86e845e7f531ae9f3e0dc).
Thus the inspected persistence mounting logic is native upstream, not a
ROCK-specific modification. This is not proof that all upstream installations
have the same shutdown symptom.

systemd 252 subsequently kills remaining processes and attempts read-only
remounts/unmounts in its final shutdown phase. It only returns to initramfs when
/run/initramfs/shutdown exists and is executable. Sources:
https://github.com/systemd/systemd/blob/v252/src/shutdown/shutdown.c
https://github.com/systemd/systemd/blob/v252/src/shutdown/umount.c

Our persistent journal ends when journald receives SIGTERM, before these final
attempts. pstore is empty. Therefore the final persistence read-only status
cannot be established from the journal. The next boot has no logged ext4
recovery or I/O errors, but this is not equivalent to an offline filesystem
check or proof of clean unmount.

Next validation should capture final shutdown over serial console (or another
verified late-boot capture mechanism), and/or inspect the powered-off card
read-only on the ThinkPad. Do not run repair or claim fsck validity on the
mounted writable persistence filesystem. Do not suppress the mount failure,
force/lazily detach the active root backing store, or add a custom initramfs
shutdown implementation before verifying native upstream behavior and the
existing final remount outcome. No persistence shutdown modification was made.

## Offline verification after regular poweroff

The card was removed after regular poweroff and inspected unmounted on the
ThinkPad as /dev/sdc (59.5 GiB SD/MMC), with no filesystem mount or repair.
Direct read-only superblock inspection on /dev/sdc3 reported state=1 (clean),
no filesystem error flag and no needs_recovery incompat flag.

Administrator-authorized `e2fsck -f -n /dev/sdc3` completed all five passes,
exit 0, with no reported inconsistencies: 10977/3883008 files,
5189340/15524091 blocks. `fsck.fat -n /dev/sdc2` also exited 0:
6 files, 75/65467 clusters. Neither check repaired or replayed the journal.

This provides evidence of a clean persisted filesystem after this tested
poweroff despite the early persistence mount-unit EBUSY message. It does not
prove physical unmount in the final stage (a successful final read-only remount
can also leave clean state), nor does it establish power-loss resilience.
No custom persistence shutdown implementation is justified by this result.
Keep the proven KVM media-release fix; treat the remaining early mount-unit
message separately from filesystem integrity and review upstream if needed.
