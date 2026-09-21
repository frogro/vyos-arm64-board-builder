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

ROCK bundle build completed (2026-09-21 02:23 UTC), source 3a8debd,
base 33a15bdf6c0411cd8692420566e3781ccdd3a80ee5665a8f2eb9b107982398a7.
Output localhost/vyarm-kiosk:runtime-bundle-20260921,
ID e4130633aed1a04d033330f0c24757218078ebf524f36f0bf70732a89135eb8a.
Build verified required binaries, Python compilation and shell syntax. Not yet
activated; next test must remove old runtime-helper bind mounts in a temporary
Quadlet so the bundled files are genuinely exercised, with independent rollback.

Bundle live test (02:36 UTC): running from the assembled image with the five
old helper/policy bind mounts removed, Xorg selected glamor, portrait and ILITEK
enumeration remained, Sunshine found H264+HEVC, five persistent Sunshine
config/state/certificate files were byte-identical. Separate browser probe passed.
However the actual kiosk browser reported render-node permission denied: unlike
the diagnostic probe, startup reset supplementary groups to the image's kiosk
memberships. Thus this was NOT a complete production GPU success. Rolled back
original image/Quadlet and verified service active. Logs/backups retained in
/config/kiosk-test/builds/bundle-live-20260921.

Source correction: startup now preserves kiosk's existing supplementary groups
and adds nonzero group IDs from explicitly granted render character devices only
when graphics=auto. Does not chmod host devices, change /etc/group, add group0 or
grant new devices. 57 tests pass including membership preservation/root exclusion.
Needs updated bundle and repeat live production-browser validation.

Bundle v2 built from ed2eb67, image
81c041f773713e65a04d4f2318624ddea0b6178a25a1d513d1729d2f235aec16,
revision label verified. Live test 02:51 UTC used bundled helpers (old helper
mounts removed), graphics auto and scoped render grant. Actual kiosk Chromium
now launches GPU and renderer processes; supplementary groups include the render
group. To validate beyond the unsandboxed diagnostic, temporarily replaced the
container-local test HTML with the WebGL probe and restarted only Chromium under
its existing supervisor. Existing production launch flags and sandbox unchanged.
Window title reported `ANGLE (Mesa, Mali-G610 (Panfrost), OpenGL ES 3.1)` with
pixel [255,0,0,255]. This establishes hardware WebGL rendering in the actual kiosk
browser, not video hardware decoding or performance. Five persistent Sunshine
files remained unchanged. Explicit rollback restored original image/Quadlet and
normal test page; service active. Logs in bundle-v2-live-20260921.

Additional nonfatal cache issue: root Xorg and user browser shared HOME/.cache.
Source now gives Xorg a runtime cache and the user session /state/cache (created
before existing kiosk ownership setup). Shell syntax checked; this cache cleanup
is not yet part of the validated v2 image and needs next bundle validation.
