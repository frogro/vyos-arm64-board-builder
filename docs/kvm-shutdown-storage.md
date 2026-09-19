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
