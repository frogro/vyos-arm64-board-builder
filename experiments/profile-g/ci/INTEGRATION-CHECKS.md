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
kiosk/receiver transitions, cold boot, physical HDMI and audio. AirPlay mirroring/photos/video/audio were accepted live with iPhone 13;
they still require a repeat in the installed image. Miracast's known
Intel sender firmware/restart issue is not solved merely by packaging G.

The full build can prepare A–D/F and its CLI while the G runtime compiles.
Assembly waits for that exact runtime and fails if it fails; it never silently
substitutes an older G artifact. No router access occurs from GitHub Actions.


## 2026-09-29 audit of uncommitted/live-only G changes

| Finding | Integration |
| --- | --- |
| Steam Link entirely absent from schema/backend/runtime | Separate pinned adapter and CLI method, device/capability/hash guards, persistent settings and H264 software fallback |
| HEVC request RPS patch existed only in live build | Exact backport and UAPI compatibility header in private decoder build; original attribution and conformance evidence retained |
| Uncommitted ordered session shutdown | Client is stopped/waited before audio, XWayland and compositor |
| Live Miracast `--use-dev` missing from recipe | Added to the existing dedicated-radio-only launch; AP ownership checks retained |
| HDMI port detection, timer-based audio and Miracast player/relink fixes | Already in committed files; compared to live copies |
| Fixed AirPlay diagnostic PIN | Deliberately excluded; random PIN and persistent register/key retained |
| ISO missing `features.receiver_g` | Added to actual manifest generator; execute-generator regression covers old and G profiles |
| FFmpeg build script excluded from Docker context | Explicit script/patch/adapter context allowlist |
| Temporary screen-sharing/input automation and snapshots | Test-only; not shipped in container |

The `live-test/steamlink` findings had not been committed on feature/profile-g;
this integration records the source experiments and measurements. Its earlier
"not integrated" entries describe their historical state; STEAMLINK.md is the
current adapter contract. Existing A–D/F code remains byte-for-byte against the
accepted test baseline in protected directories; main's 31 packages and eight
A–D combinations are checked independently.

Acceptance still open: SD installation and ISO upgrade of this exact combined
artifact; AP, Tailscale identity, Sunshine/AirPlay/Steam pairing retention after
update; extended multi-sender soak; physical HDMI hotplug/fault transitions.
Google Cast is not implemented. USB redirection and AV1 are not qualified.
The previous installed image and kiosk configuration remain the recovery path.

Residual live warning: isolated `HDMI: Unknown ELD version 0` on codec.7 around
transitions; the old repeated ASoC prepare-error flood was not observed. This
remains an explicit acceptance gap, not a passing HDMI hotplug result.

### Receiver decoder selection and memory diagnostics (2026-10-04)

`show display-receiver media <container>` reports visible decoder/heap grants,
CMA in KiB, requested policy, startup selection and available Miracast stream
observations. Capability discovery and startup selection are not stream proof.
Miracast records the decoder only after a decoded buffer reaches its sink;
presentation and remote input still require a complete sender test.
`show kiosk media <container>` additionally reports current CMA totals/free space.
Neither command changes decoder or boot settings.

G discovers H.264 V4L2 factories and enumerates frame sizes on the granted device.
It prefers the broadest eligible decoder, independent of `/dev/videoN` numbering.
Auto ranks unsuitable factories below software; hardware mode refuses an
ineligible stateless decoder. Miracast uses the negotiated `-r` dimensions.
Its protocol negotiation does not use the generic receiver resolution/fps fields
and the pinned MiracleCast mode table does not advertise 4K.

Moonlight explicitly selected H.264 and HEVC use the private Request libraries.
Auto with hardware permitted conservatively selects H.264; explicit AV1 and
software mode retain system libraries. The private FFmpeg build only includes
H.264, HEVC and AAC, so it must not be applied unconditionally to AV1.
Steam Link retains its 1080p60 H.264/HEVC limits.

The private FFmpeg includes the stable Linux UAPI NV15 FOURCC when older build
headers omit it. The definition matches Linux 6.18 `videodev2.h`; runtime format
negotiation remains mandatory. This enables packed 10-bit capture without
replacing system FFmpeg, GStreamer or kernel headers. Source:
https://github.com/torvalds/linux/blob/v6.18/include/uapi/linux/videodev2.h

Local ROCK 5B validation used kernel 6.18.54 and 512 MiB CMA. The new FFmpeg
actually decoded the 3840x2160 Main10 sample through rkvdec to `drm_prime`, with
300 decoded frames and zero decode errors; the previous binary fell back to CPU.
This is a decoder test, not HDR output or a complete Moonlight/Steam Link test.
