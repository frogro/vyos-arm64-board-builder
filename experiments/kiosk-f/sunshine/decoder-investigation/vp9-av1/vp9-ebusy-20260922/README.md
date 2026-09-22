# VP9 plus EBUSY-removal: controlled live comparison, 2026-09-22

ROCK 5B, running 6.18.50-vyos-f-test3, no reboot. AV1 test4 kernel build
continued independently. Production module files and build defaults unchanged.

## Variants and reproduction

A: signed external module from ../vp9-live-20260922 (four-part VDPU381 VP9
series, existing H.264/HEVC safeguards retained).
B: same module plus removal of vb2_is_busy()/EBUSY in rkvdec_s_ctrl when the
image format changes. No other source difference. This is the existing
Armbian patch by Jianfeng Liu, not a new driver fix developed here; source:
../../armbian-7.1-h264-hevc/armbian-rkvdec-remove-busy-check.patch.
The included ebusy-on-vp9.patch records the exact delta on the VP9 source.

Built using the existing matching test3 source/output, external M= directory,
ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- CONFIG_VIDEO_ROCKCHIP_VDEC=m,
-j1 modules; signed with the existing test3 signing key. Module hashes included.
Private signing material is not included.

run-compare.sh records the live procedure and existing fixture/tool paths.
It checks zero module references before switching, resolves decoder nodes from
the platform device and restores the installed module on exit. No force unload.
Raw browser JSON remains under /config/kiosk-test/kernel-test3/vp9-ebusy-compare
on the ROCK; comparison.json retains metrics, decoder selection and flags.

## Results

Both variants passed three exact I420 reference comparisons each for H.264 and
HEVC using test-stateless-decode.sh. These are decoder-output tests, with an
explicit V4L2 stateless decoder in GStreamer and no software fallback. Both
also passed all 300 per-frame NV12 hashes for the 5-second VP9 Profile0 fixture.

Independent sandboxed Chromium153/Weston16 runs, same fixed fixtures and flags,
1080p60, 30 seconds, 1,800 frames per run:

| Codec | A: VP9, EBUSY retained | B: VP9, EBUSY removed |
|---|---:|---:|
| H.264 | 263 dropped | 259 dropped |
| H.265 | 4 dropped | 7 dropped |
| VP9 | 11 dropped | 8 dropped |

All six runs ended and reported V4L2VideoDecoder, platform=true. No additional
relevant kernel warnings/errors; only the known ignored second decoder core.
Afterward original installed module restored (S264/S265 only), refcnt zero,
and only kiosk-test remains running. Evidence in restored.txt and kernel.txt.

## Interpretation and limits

No regression detected in these fixtures. Removing the guard does NOT resolve
the known H.264 B-pyramid playback problem. Small single-run differences are
not evidence of a performance benefit or regression. VP9 browser fixture is
six repeats of the same 5-second source, not broad content coverage.

The removed check is conditional on image-format change, not per-frame timing.
These fixed-format tests do not prove safe in-session format changes, nor prove
that the old EBUSY branch was exercised. Bit-depth/chroma changes with allocated
capture buffers, Main10/NV15, resolution changes, malformed streams, seek/reset
stress and longer repeats remain needed before enabling it by default.
Browser decoder selection and drop counters are not pixel-exact output checks.
No change to profile D transport/encoding; these results concern the ROCK's
local decode/browser path for F. Neither variant is enabled in the AV1 test4
build or the standard image workflow by this experiment.
