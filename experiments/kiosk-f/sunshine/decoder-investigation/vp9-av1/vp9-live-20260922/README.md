# Live VP9 VDPU381 experiment, 2026-09-22

Unchanged running 6.18.50-vyos-f-test3, no reboot. External signed rkvdec module
built with the exact test3 source/output and signing key. AV1 test4 full build
continued independently. No production module files or workflows changed.

## Source

Original four-part mailing-list series:
https://lists.openwall.net/linux-kernel/2026/07/26/761
Message-ID 20260726-b4-add-rkvdec2-vp9-vdpu381-v1-0-180fb2d1f10c@gmail.com.
Apply order: helper rename, common-code split, VDPU381 backend, 64-byte stride.
Only rejected context was an archive-obfuscated email in a copyright comment;
resolved manually retaining authorship. No code conflict. Combined delta and
hashes retained here. Original test3 HEVC safeguards retained. No EBUSY-removal,
PM reorder or additional reset patch mixed into this experiment.

Compile passed using external M= rkvdec directory, ARCH=arm64,
CROSS_COMPILE=aarch64-linux-gnu-, CONFIG_VIDEO_ROCKCHIP_VDEC=m, -j1.
Module signed with existing test3 key; no private key included in repository.

## Live results

- Confirmed no users of /dev/video2 or matching media node, module refcnt zero.
- Each test temporarily unloaded baseline and loaded signed test module;
  VP9F appeared alongside S264/S265. Device paths resolved from platform node.
- First pipeline failed before decode because minimal image lacked Matroska
  demuxer; IVF parser also absent. Baseline restored after failure.
- Lossless remux to IVF and a small GStreamer appsrc feeder bypass missing
  demuxers. It preserves frame boundaries and IVF timing, then uses vp9parse,
  v4l2slvp9dec and raw NV12 output. No software decoder in that pipeline.
- Two independent load/decode/unload runs: 300/300 frames each match SHA256
  per-frame NV12 FFmpeg software references, 1920x1080,60fps,VP9 Profile0 8-bit.
- Sandboxed Chromium153/Weston16: 5s ended,300 frames,9 drops, hardware
  V4L2VideoDecoder/platform=true.
- 30s fixture (six repeats of the same 5s clip, lossless remux): ended,
  1800 frames,17 drops (~0.94%), V4L2VideoDecoder/platform=true.
- Original module restored after tests: only S264/S265 exposed again. Only
  kiosk-test container remains. Relevant final kernel log has no decode,
  IOMMU or ACK fault; second decoder core still deliberately ignored.

## Limits / next checks

Profile2/Main10,NV15,resize/segmentation/altref conformance suites, long soak,
error recovery and physical display correctness remain untested. Browser
hardware selection/frame count is not a pixel-exact browser-output test.
30s repeated fixture is not representative of all internet VP9 content.
No full H264/HEVC regression suite was run with this module; required before
integration because shared VP9 code and capture stride changed.

The scripts keep baseline-on-exit cleanup. Cleanup was hardened after the
successful tests to restore baseline even if insmod itself fails; it refuses
to force-unload a busy decoder. That failure branch is syntax-checked, not
fault-injection tested. A hard kernel hang still requires external reset.
This remains an optional experiment, not enabled in AV1 test4 or profile F.
