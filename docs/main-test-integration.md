# Shared main-test integration

`main-test` is the shared integration branch for all boards. It starts from the
latest common E52C branch, which already contains the ROCK 5B MPP/KVM work and
Pi development, and merges the remaining remote branch histories. `main` has
not been changed. Future board tests can select `main-test` with explicit board
and profile workflow inputs; a push here does not publish a board image.

## Branch audit, 2026-09-14

| Source | Reviewed head | Result |
|---|---|---|
| `origin` | `021a0deead51` | Included in ancestry |
| `origin/e52c-vendor-uboot-test` | `f1f81268aa75` | Included in ancestry |
| `origin/fix-grub-board-dtb-persistence` | `11888c4d10cf` | Included in ancestry |
| `origin/fix-system-image-dtb-update` | `2d478807868f` | Included in ancestry |
| `origin/generic-board-image-pipeline` | `beef466eeae4` | Included in ancestry |
| `origin/main` | `021a0deead51` | Included in ancestry |
| `origin/pi5-test-20260819-1` | `25f85ab77ef0` | Included in ancestry |
| `origin/rock5b-build-20260913-110238` | `e1c344ab5fe1` | Included in ancestry |
| `origin/rock5b-fc400000-gadget-test` | `c4a19c551507` | Included in ancestry |
| `origin/rock5b-mpp-6.18-test` | `e50926f28dc6` | Included in ancestry |
| `origin/test-bootchain-first` | `a9574c12ff48` | Included in ancestry |

## Merge decisions

- ROCK MPP: merged normally. Its Quectel commit is equivalent to the already
  integrated commit; the asset exists once, enabled only by Extended Network.
- DTB fixes: retained identical GRUB support and the newer system-image updater
  with native boot metadata validation. The add/add conflict retained that
  newer implementation.
- Temporary ROCK push trigger: history incorporated without reintroducing the
  hard-coded old raw run, Armbian pin or implicit all-profile build settings.
- Bootchain-first experiment: history incorporated without reintroducing its
  obsolete pre-provider workflow ordering. The dedicated bootchain workflow
  remains available for isolated bootchain work.

## Board and update boundaries

The E52C-tested identity fallback is installed only for E52C in board images and
update ISOs. ROCK 5B and Pi identity/firmware behavior is unchanged. Quectel A04
is an optional, inactive asset for all boards with Extended Network. Existing
releases and in-flight runs retain their original commit and are not changed.

## Path to main

Run the shared automated checks, then build and hardware-test ROCK 5B, Pi 5 and
E52C profiles from this branch, including their respective update/default/return
paths. Hardware identity and DHCPv6 acceptance across image changes remain
separate checks. Native CLI source integration and the optional Tailscale CLI
remain roadmap items, not completed functionality.

After reviewing these results, merge main-test into main and use short-lived
feature branches. No old branch or historical local source tree is deleted by
this consolidation. Uncommitted local experiments are not automatically merged;
the supplied Quectel change has been explicitly included.

## Local validation

All 20 Python test programs passed. Common firstboot, KVM selection/native CLI,
and persistence resolver shell checks passed. All workflow files passed
`actionlint`; `git diff --check` passed. No new full image build or hardware
acceptance was performed for main-test during this consolidation.
