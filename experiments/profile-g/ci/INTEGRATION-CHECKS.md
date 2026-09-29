# A–D/F/G image acceptance gates

Reference A–D/F source: `dba06ef52ebcb081e4e2725ab9b17a90c25f0671`, successful
GitHub run `36384286092`. G is additive; main is not changed by this workflow.

| Area | Build gate |
| --- | --- |
| Established A–D behavior | main-preservation checker, native KVM/CLI/input/supervisor tests |
| F source preservation | exact comparison of container, Sunshine patches, image, host and systemd sources against the successful A–D/F source |
| Chromium | original binary SHA256 enforced in F runtime build; crash handler retained |
| Sunshine | same pinned source, MPP/RGA, portrait, input mapping and HEVC patches as A–D/F; library and audio tool checks |
| D conversion paths | cached-copy helper built natively and compared in final rootfs; existing supervisor and CLI tests retained |
| Native CLI | pinned VyOS source prepared with all four profiles, independent reviewed G recipe, package/schema owner checks |
| Kernel and boot | same audited kernel input, optional Panthor artifact with unchanged build inputs; kernel/DTB/initrd SD-versus-ISO comparison and firmware checks |
| F and G runtimes | both complete archives compared inside the final squashfs; G only accepted from a successful same-commit parallel build |
| G activation | only offline importer enabled; no receiver container service enabled automatically |
| State preservation | staging/import tests preserve sample config.boot, Tailscale state, Sunshine pairing and existing F archive; no live user data copied into images |
| Artifact integrity | filesystem check, internal ISO checksums, compressed-image test, final checksums and provenance/inventory before upload |

A build pass is not an installed-system acceptance. After installation, verify
AP configuration, Tailscale device identity, Sunshine/Moonlight pairings,
kiosk/receiver transitions, cold boot, physical HDMI and audio. AirPlay has a
built UxPlay receiver but still needs an Apple sender test. Miracast's known
Intel sender firmware/restart issue is not solved merely by packaging G.

The full build can prepare A–D/F and its CLI while the G runtime compiles.
Assembly waits for that exact runtime and fails if it fails; it never silently
substitutes an older G artifact. No router access occurs from GitHub Actions.
