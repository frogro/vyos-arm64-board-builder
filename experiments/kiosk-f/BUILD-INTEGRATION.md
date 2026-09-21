# Experimental F package and image integration

Opt in explicitly on feature/kiosk-profile-f:

```
KIOSK_F=yes KIOSK_F_GPU_FIRMWARE=mali-arch10.8 tools/assemble-board-image.sh <board> <branch> <raw> <output>
```

This uses the same image assembly implementation locally and on a future F image
runner. Default KIOSK_F=no preserves the existing image selection. The existing
release workflows are unchanged; kiosk-f-checks.yml only runs tests on this branch
or manual dispatch and never builds/publishes an image.

When enabled, assembly builds a matching complete vyos-1x package with kiosk and
Sunshine CLI (plus independently selected KVM/Tailscale), validates package
contents/profile provenance, and installs it before board finalization. It then
stages rsyslog guard, selected GPU firmware/licence/initramfs hook and protects
board DT template with a dpkg diversion before generating initramfs/squashfs.
Image updates use this same assembled rootfs; old overlay files are not assumed
to migrate. Rerun protect-grub-dtb after live package upgrades to refresh from
upstream while preserving explicit DT selection.

Select GPU firmware by supported GPU architecture, not by a board-name heuristic.
`none` is suitable when no Panthor firmware is required. Panthor-enabled F kernels
require an explicit supported selection; currently mali-arch10.8 is implemented.
This switch does not enable kernel options or claim support for another SoC.

CLI source generation resolves stable by-id/by-path inputs to their current evdev
destinations for kiosk containers. It preserves saved configuration, grants no
new devices, rejects absent devices/collisions and leaves non-kiosk mappings
unchanged. Resolution occurs on native generation/commit/boot, not continuous USB
hotplug: the experimental watcher remains separate and disabled on the ROCK.

Remaining full F deliverable: immutable kiosk/Sunshine image packaging and initial
provisioning, complete board kernel feature selection, actual full image build,
first-install/update boot validation, and a dedicated image-release workflow.
These changes wire the host/CLI fixes; they do not claim all of F is finished.
No live CLI package replacement was performed by this integration change.

## Combined runtime layer

`container/Containerfile.bundle` assembles current startup, display/touch,
Sunshine policy helpers and defaults over an explicitly selected codec image.
Pass BASE_IMAGE as an immutable image ID/digest and SOURCE_REVISION as the source
commit, with container/ as context. No host devices, saved configuration or state
are copied. Graphics defaults to software; explicit auto remains a deployment
choice with separate scoped device grants. The same layer is usable over other
compatible SBC codec images; it performs no board-name dispatch.

This consolidates previously separate helper layers; it does not yet make the
experimental codec base independently reproducible from a public registry or
complete offline first-install/update image provisioning. Do not call this a
finished full F image pipeline.
