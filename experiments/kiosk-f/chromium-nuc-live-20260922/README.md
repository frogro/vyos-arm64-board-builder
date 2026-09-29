# Chromium 153: decoder, P010 and color validation — 2026-09-22

## Result and boundary

The NUC-built ARM64 browser decodes H264, HEVC/Main10, VP9/Profile2 and AV1
8/10-bit through V4L2 in an isolated sandboxed Chromium/Weston16 container on
ROCK5B. This does not establish all-content, HDR, physical-panel, direct-overlay,
4K or long-term production readiness. AV1 still uses the test4 diagnostic
reset/PM workaround; the browser corrections do not fix that kernel issue.

Latest tested browser SHA256:
`d1f979a39d0402060364e5a9202cb6e8772a7e3ec90c91622151defcb851eeb6`.
Production browser/CLI defaults/main/release workflows unchanged. No push.
Temporary modules restored; Hantro unloaded, driver overrides cleared, rollback
and reboot timers canceled. Kiosk, input reconciler and D video service active.
Only production kiosk-test container remains. Test4 stays running; normal boot
default unchanged, GRUB next_entry empty. See final-live-health.txt.

## Reproducible browser changes

Apply followup-patch-series.json after the original unified recipe under
../sunshine/decoder-investigation/chromium-unified-20260922. Original recipe
includes H264 reserve, NV15 Chromium/ANGLE/import support and HEVC SPS/RPS controls.

1. AV1 gets its own `V4L2ExtraAV1CaptureBuffers` feature, independent of H264's
   `V4L2ExtraCaptureBuffers`. Both disabled by default; extra_buffers default2,
   clamp0..8, capped VIDEO_MAX_FRAME; stateless requests/MMAP/non-low-delay only.
   No blanket HEVC/VP9 reserve increase and no board-name assumptions.
2. VideoDecoderPipeline previously discarded the low_delay argument. Forward
   it for V4L2 only, retaining previous behavior for other decoder backends.
3. `NativePixmapAccurateYuvMatrix` optionally requests REC709 for BT709 EGL
   imports instead of the legacy REC601 overlay-compatibility policy. Disabled
   by default. BT601/2020 and range handling remain unchanged. Do not globally
   enable before physical/direct-overlay validation.
4. P010 single-buffer layouts now derive UV byte stride/offset from the driver's
   bytesperline, including padding. This is an internal generic format fix,
   not a user switch. It resolves the observed AV1 10-bit FrameResource failure.
5. Regression expectations follow the pre-existing Linux LINEAR modifier
   policy; non-Linux expectations remain unchanged. This last patch is test-only.

Source/artifact manifests and build scripts are retained. Runtime support
libraries/resources match NUC and ROCK. All older binaries are preserved.

| Candidate | SHA256 | Build result |
|---|---|---|
| Initial unified |159775efbda4666bf9873ca63a3f48eff1d4fb62ba7cbf0c0500c5f37f1bf700|completed original build|
| AV1 reserve |0da9adc06a8421abcafe8082afa3ce8a147bf944d8117e72f0537f561f276ca2|incremental exit0,13:47–13:51CEST|
| Low-delay forwarding |ddde5d9427dd3b701526a6e8dc3d4bc6f3575a77ed9e99b18a5b214b1f9863a8|incremental exit0,14:04–14:08|
| BT709 opt-in |3ba6a8dfa5dedc40fa6877884621b7640fdddacde17f27cc1ddd5e2b32d4e746|incremental exit0,15:00:49|
| P010 layout |d1f979a39d0402060364e5a9202cb6e8772a7e3ec90c91622151defcb851eeb6|incremental exit0,15:08:41|

NUC /home/photobooth/vyarm-chromium-build/source-cross, native x86 cross compiler,
8jobs,26GiB memory/30GiB total,16CPU quota. Dedicated Docker socket. Each browser
follow-up executed about494 Ninja steps without a clean/full rebuild. The separate
media_unittests target required1385 additional steps. All nine V4L2UtilsTest tests passed at15:28CEST, including the new padded-stride
P010 case. The initial run passed6/9: three existing tests expected an invalid
modifier sentinel despite the existing Linux linear-modifier implementation.
The separate test-only patch corrects those expectations (Linux only); both
initial and final logs are retained. No browser rebuild is needed for that
test-only adjustment.

## Playback evidence

Headless Weston GL1920x1080, kiosk user, sandbox retained, no LD_PRELOAD buffer
interposer. CDP V4L2VideoDecoder/platform=true is the hardware evidence. Drops
are presentation counters, not network packet loss. CPU is whole browser/compositor
cgroup usage as percent of one CPU; runs are sequential, not statistical benchmarks.

| Test | Frames / drops | Notes |
|---|---|---|
| H264 reserve off, initial browser |1800 /259,277|same fixture|
| H264 reserve on |1800 /6,5|initial browser|
| Final H264120s, summary+HTTP Range |7200 /13|CPU58.3%,page120.315s|
| Matching H264 software |7200 /39|CPU155.4%,page120.314s|
| HEVC8-bit |1800 /4|combined-module later2drops|
| Main10 short |300 /3|stock Debian153 failed SetupOutputFormat|
| Main10120s, summary polling |7200 /23|CPU61.4%,Media play→end120.19s|
| HEVC RPS sample |44 /2|EOS,not full conformance proof|
| VP9 Profile0, combined module |1800 /6|native300 hashes match software|
| VP9 Profile2 10-bit |1800 /8|hardware; color initially inaccurate, see below|
| AV1 reserve off |7200 /984|same AV1 browser binary as next row|
| AV1 reserve on |7200 /70,60|CPU68.9/70.1%;10→12 capture buffers|
| AV1 software8-bit |7200 /63|CPU163.6%,Dav1d/platform=false|
| AV1 final low-delay candidate |7200 /69|reserve on|
| AV1 10-bit after P010 fix |1800 /6|CPU63.6%,V4L2/platform=true|
| Matching AV1 10-bit software |1800 /46|CPU247.4%|
| AV1 8-bit P010 regression |300 /1|EOS|

Additional checks: five H2641080p↔720p source changes; eight forward/backward
seeks each for H264 and Main10 (presented frames within34ms of target);
H264 high-reference fixture600frames/6drops; one-session codec reuse
AV1→H264→HEVC→Main10→AV1, repeated after low-delay correction. No-device AV1
fallback works with reserve flag enabled. Earlier H264 page elapsed125.1/123.1s
includes startup; Media play→end120.11s, not evidence of a three-second playback pause.

WebRTC20s initially requested6/8buffers off/on despite intended low_delay guard.
After forwarding fix both request6, decode1147/1162frames with0packetloss.
This tests the receiver, not D's capture/encoder performance or physical latency.

## Color evidence and limits

Native VP9 10-bit decoding had prior bitexact evidence, but browser canvas output
was closer to BT601 than BT709. Source explicitly selected REC601 for BT709 EGL
imports. Opt-in correction compared against explicit FFmpeg BT709 RGB references:

| Sample | Mean absolute RGB error off→on (0–255) |
|---|---|
| HEVC Main10 BT709 limited |7.107→1.408|
| VP9 Profile2 BT709 limited |7.279→0.948|
| HEVC Main10 BT709 full, explicit colr |7.120→0.711|
| AV1 10-bit P010, feature on |0.778|

BT601/SMPTE170M limited with explicit container metadata is pixel-identical off/on.
Initial range/matrix fixtures lacked MP4 colr tags and had incomplete bitstream VUI;
Chromium reported BT709/LIMITED for intended other variants. Those runs are retained
but excluded as intended-matrix/range regression evidence. Corrected colr fixtures
are confirmed through CDP SMPTE170M/LIMITED and BT709/FULL properties.
Incomplete metadata inference remains separate. Canvas is 8-bit RGB; this does
not prove physical 10-bit/HDR output or exact RGB equivalence with color management.

## Kernel isolation

Running6.18.50-vyos-f-test4-av1-iommu. AV1 uses original test4 Hantro with diagnostic
remove-reset mask0 and other-core overrides, not the failed PM-v5 candidate.
Hantro unloaded successfully after AV1 runs; overrides cleared. AV1 PM/reset
correctness is still a shipping gate, independent of working browser playback.

VP9 absent from default test4. Existing validated VP9/RCB/B1/RPS external sources
were rebuilt together against test4 with matching vermagic and trusted signing
key (never copied into artifacts). Temporary videodev/v4l2-h264/rkvdec modules
were used with independent restoration timers, then original modules restored.
Reused for Profile2 and color checks with separately recorded restoration paths.
No installed kernel modules were overwritten. Modem untouched.

## Harness corrections and next integration

Use run-p010.sh/probe-color.py for latest browser tests: summary-only CDP polling
avoids retransmitting an ever-growing frame list; HTTP single-range206 supports
seeking. Seek fixture discards stale callbacks until target frame arrives.
Old full-list Main10 run83drops improved to23 with summary polling; do not treat
differing harnesses as identical benchmarks. An earlier active-runner edit caused
exit127/emptyJSON; excluded. Versioned runners used afterwards. Trimmed ROCK FFmpeg
could not remux MP4, so local FFmpeg produced the Main10 fixture; no decoder failure
inferred from remux-tool limitations.

Local checksum-backed runtime archives live under builder tmp/chromium-final-20260922
and tmp/chromium-p010-color-20260922. They are experimental artifacts requiring the
compatible container runtime/device permissions, not published/installable releases.
Future CLI capability detection, fallback and config retention are recorded in
../MEDIA-CLI-PLAN.md. Do not force these flags on unrelated SBCs or receiver browsers.
