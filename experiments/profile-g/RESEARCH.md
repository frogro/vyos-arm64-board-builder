# Receiver research, 2026-09-28

## Decisions linked to upstream evidence

- [UxPlay upstream](https://github.com/FDH2/UxPlay): GStreamer video/audio sinks,
  decoder selection, PIN registration and persistent key files allow an
  independent receiver with durable /state. Source pinned at
  8f40118b1a72d7e16ce684b0f3ce6a0ae32bdc79. Start with H264 mirroring; do not
  transfer Chromium-specific buffer switches to unrelated decoder stacks.
- [Moonlight Qt upstream](https://github.com/moonlight-stream/moonlight-qt) and
  [CLI implementation](https://github.com/moonlight-stream/moonlight-qt/blob/8369d1a0e11b999d4d1598f62ca5f6dea49602fb/app/cli/commandlineparser.cpp):
  use the actual stream/host/app options, codec names and decoder choices.
  Build from 8369d1a0e11b999d4d1598f62ca5f6dea49602fb including pinned submodules.
- [MiracleCast upstream](https://github.com/albfan/miraclecast): explicit
  --interface, sinkctl run LINK and external-player support. Source pinned at
  0b7f1f1f6586dc65ff480f3cda5c2170a70aa020. Avoid the upstream quick-start's global
  shutdown of network services on a router. Replace the example player's
  unlimited queues with bounded queues; run media playback unprivileged.
- [Maintainer discussion #271](https://github.com/albfan/miraclecast/issues/271)
  and [report #529](https://github.com/albfan/miraclecast/issues/529): a Wi-Fi
  Direct connection is not by itself a successful Miracast stream; Samsung
  source behavior needs a real SmartView/DeX test. Reports motivate tests,
  not unconditional driver changes.
- [MediaTek mailing-list P2P support patch](https://lists.infradead.org/pipermail/linux-mediatek/2023-January/054250.html):
  MT7921 P2P client/GO support explicitly accounts for firmware connection
  types. [Channel-context discussion](https://lists.infradead.org/pipermail/linux-mediatek/2022-August/047100.html)
  documents concurrent-role complexity. [MT7925 P2P fix discussion](https://www.spinics.net/lists/linux-wireless/msg260540.html)
  shows that P2P is a supported but evolving path. Inspect the running PHY;
  don't add historical patches blindly to our newer kernel.
- [Valve Raspberry Pi instructions](https://help.steampowered.com/en/faqs/view/6424-467A-31D9-C6CB)
  document a Pi deployment, not tested RK3588 support.
  [Valve developer forum reply](https://steamcommunity.com/app/353380/discussions/6/4697909023281926501/)
  points to newer Pi 5 beta support: old forum claims of no ARM64 support must
  not be generalized. [2026 native ARM64 report](https://steamcommunity.com/app/353380/discussions/10/571544346711605626/)
  reports decoder integration failures on another SoC, not a ROCK result.
  Keep Steam Link unadvertised until a suitable distributable runtime is tested.
- [Google receiver model](https://developers.google.com/cast/docs/overview):
  a Web Receiver runs on a Cast-enabled device; an ordinary Chromium page is
  not equivalent to a Chromecast receiver. No working G implementation claimed.

All of these are external technical references, not instructions to change
router network ownership or disable existing services.

## 2026-09-28: Miracast A/V stutter after decoder comparison

User confirmed equally stuttering video/audio with v4l2slh264dec and
avdec_h264. Software comparison measured approximately 6–12 displayed fps
(about 7 average); low CPU does not establish a decoder throughput limit.
AAC was previously absent on the sender: installing gstreamer1.0-libav and
routing Firefox to the GNOME Network Displays sink enabled actual audio.
The larger diagnostic RTP/TS buffers did not resolve stuttering. Kiosk and
hostapd restored after comparison. These diagnostic settings are not a
validated replacement for the repository defaults.

Research candidates, not verified fixes:

1. Receiver queues currently permit only 100 ms (video additionally four
   buffers). Inspect backpressure and input PTS cadence before changing more
   decoder settings. Compare coordinated multiqueue buffering or larger
   independent queues, preserving clock synchronization. Official rationale:
   https://gstreamer.freedesktop.org/documentation/coreelements/multiqueue.html
   https://gstreamer.freedesktop.org/documentation/tutorials/basic/multithreading-and-pad-availability.html
2. Isolate the sender encoder independently with the supported
   NETWORK_DISPLAYS_H264_ENC override (x264enc versus vah264enc, after checking
   availability). GNOME 0.99.0 already configures x264 ultrafast/zerolatency;
   this is a diagnostic alternative, not a reason to abandon hardware decode.
   https://github.com/GNOME/gnome-network-displays/blob/master/README.md
   https://github.com/GNOME/gnome-network-displays/blob/0.99.0/src/wfd/wfd-media-factory.c
3. HDMI selection fixed the unused-port ELD errors. Separate ALSA POLLOUT /
   snd_pcm_avail warnings remain a timing candidate. Test tsched separately,
   not together with queue and encoder changes. A mailing-list report has
   similar messages but concerns USB echo cancellation, NOT our Rockchip HDMI
   path; it does not prove either cause or a usable patch:
   https://www.mail-archive.com/pulseaudio-discuss@lists.freedesktop.org/msg21396.html
4. Ubuntu A/V discussion concerns local audio versus remote video and does
   not solve simultaneous remote A/V stutter. Do not adopt its fixed 700 ms
   local-audio delay as our fix:
   https://discourse.ubuntu.com/t/miracast-a-v-sync/67516

No matching verified Linux kernel patch found in this search. Next useful
measurement: bounded input RTP/TS cadence and sequence-gap capture alongside
queue levels and output fps, then change one variable per comparison.

### Live multiqueue comparison

Replaced only the two independent 100 ms queues with one multiqueue
(max-size-buffers=0, max-size-bytes=0, max-size-time=1000000000), using
explicit sink_0/src_0 for H.264 and sink_1/src_1 for AAC. Kept avdec_h264,
vah264enc sender, RTP 200 ms, tsdemux 200 ms, Pulse 100 ms and tsched=0
unchanged from the software baseline. This tests coordinated buffering AND
a larger queue allowance together; it does not isolate which caused the gain.
Last measured output: 3183 rendered, 0 dropped, average 29.73 fps.
Previously roughly 7 fps. ALSA POLLOUT warning remains. User assessment of
audio smoothness and A/V sync is pending; fps alone does not verify it.
Diagnostic candidate retained on ROCK as miracle-player-probe.py; repository
production defaults not changed by this comparison. Raw log is local:
/mnt/entwicklung/tmp/profile-g-live-20260928/multiqueue-av.log

### User correction and follow-up capture

User rejects multiqueue playback acceptance: long visible video outages while
sound continued, plus audio-related start messages. Counter fps is insufficient
and must not be described as smooth physical presentation. Candidate NOT accepted.

F's extra H264/AV1 capture buffers are Chromium implementation patches, not
GStreamer settings. H264 reserve is a potential analogous optimization only;
last failure used avdec_h264 and cannot be explained solely by hardware capture
pool exhaustion. AV1/P010 changes do not apply to this 8-bit H264 stream.

Follow-up tee/filesink diagnostic did not produce video or recorded bytes;
user confirmed no picture. It is an invalid playback comparison, likely a
new preroll/blocking issue, not evidence about the previous playback failure.
Rolled diagnostic tee back and restored kiosk/AP.
Independent tcpdump captured 4942 RTP packets in 12 seconds, no sequence gaps
in captured packets. Extracted 6.5 MB TS: H264 1080p30 + AAC. Local FFmpeg
software decode processed 331 frames in about 0.57 s. Missing PPS at the start
and damaged final frame may be capture-boundary artifacts. Freeze detector
found static spans, but source screen motion was not controlled, so this does
NOT locate the cause of the observed outages. Need a continuously moving
reference source before using this as upstream freeze evidence.

Alternative verified upstream: MiracleCast res/miracle-vlc invokes VLC with
rtp://@:PORT. VLC/mpv/FFmpeg executables were not found in the current G image
inspection. mpv hardware decoding requires compatible FFmpeg/device backend;
not an automatic reuse of Chromium's decoder patches.
https://raw.githubusercontent.com/albfan/miraclecast/master/res/miracle-vlc
https://github.com/mpv-player/mpv/wiki/V4L2-drmprime-support

### VLC comparison, 2026-09-28 18:28–18:34 CEST — FAILED

Installed Debian VLC 3.0.24 in isolated derivative image. Original native
Wayland attempt failed to open a window: VLC 3 xdg_shell expects the obsolete
xdg_shell interface, while Weston advertises xdg_wm_base. Upstream source:
https://raw.githubusercontent.com/videolan/vlc/3.0.x/modules/video_output/wayland/xdg-shell.c

Second diagnostic used XWayland rootful :9, VLC xcb_x11, PulseAudio,
--network-caching=500 and --avcodec-hw=none. Same GNOME sender and MiracleCast
transport. User confirmed sound but long video freezes/outages. Therefore VLC
is NOT accepted and GStreamer's receiver alone is not an adequate explanation.
Sender, transport contents/timestamps and compositor/display remain shared
candidates. This test does not identify which one is responsible.

Logs: six late-picture warnings, one late-audio warning, one way-too-early
audio warning and one ALSA false-wakeup warning. No NEW Unknown ELD / ASoC /
hdmi-audio-codec kernel errors from 18:28 through teardown. Previously found
Unknown ELD / -19 kernel messages are timestamped 17:47:17; resurfacing console
text is plausible but not visually proved. ALSA snd_pcm_avail/POLLOUT warning
is reproduced with VLC and thus not specific to GStreamer.

Kiosk and AP restored, sender stopped, homebase restored; live session/player
mounts restored to pre-VLC state. Diagnostic images retained separately.
No production default, main merge or build change. Local logs:
/mnt/entwicklung/tmp/profile-g-live-20260928/vlc-first.log
/mnt/entwicklung/tmp/profile-g-live-20260928/vlc-xwayland.log
/mnt/entwicklung/tmp/profile-g-live-20260928/vlc-kernel-start-stop.log

### Sender encoder isolation, 2026-09-28 18:36 CEST — bounded comparison

Controlled source: moving ball plus time overlay. Synthetic encoder checks
encoded and decoded 450 distinct 1080p30 frames in each case: Intel vah264enc
15.17 s, OpenH264 15.21 s, x264 15.08 s; no decode errors in these complete files.
This confirms short-run throughput only, not sustained desktop A/V playback.

Independent receiver-side RTP captures, avoiding a blocking player tee:

| Actual live encoder | RTP packets | Sequence breaks | Decoded / unique frames | Max identical run | Max PTS gap |
| --- | ---: | ---: | ---: | ---: | ---: |
| Intel VA | 6080 | 0 | 443 / 443 | 1 | 33.3 ms |
| x264 | 1644 | 0 | 409 / 406 | 2 | 33.3 ms |

15-second captures start mid-GOP; missing initial PPS and truncated final frame
must not be counted as demonstrated transport corruption. Decodable PTS spans
were 14.733 and 13.6 seconds respectively. Frame uniqueness measured after
scaling to 320x180. Neither interval shows a sustained upstream frozen image.
No user-visible receiver playback or A/V-sync acceptance was obtained here.

Installed GND 0.99.0 ignored NETWORK_DISPLAYS_H264_ENC=x264enc: its logs still
selected vah264enc. Corrected the initial capture's local name to
encoder-va-actual.pcap. True x264 selection was then verified in logs using a
process-local diagnostic LD_PRELOAD factory filter (gnd-encoder-probe.so).
This is NOT a production solution. OpenH264 selection was also logged, but
its live connection failed during P2P setup; no valid live media comparison.
That failure does not establish an encoder defect.

Installed gstreamer1.0-plugins-ugly locally for the x264 diagnostic. Test-only
preload applies only to the transient sender service. No main/default/build
changes. Artifacts remain private and local under:
/mnt/entwicklung/tmp/profile-g-live-20260928/
encoder-bench/, encoder-va-actual.*, encoder-x264-real.*,
encoder-bench.py, analyze-encoder-capture.py, gnd-encoder-probe.c.

Conclusion: no general encoder throughput problem reproduced. Intermittent
sender/source behavior remains possible; next useful isolation is synchronized
receiver presentation tracing against captured moving content, followed by the
same controlled YouTube workload. Do not label Miracast fixed based on these
short captures. Sender/pattern stopped and recovery invoked after the tests.

### Receiver display isolation, 2026-09-28 19:01–19:06 CEST

Replayed the same 15-second encoder-va-actual.ts on ROCK, independent of WLAN
and live sender. Isolated receiver session, recovery timer armed; temporary
python3-gi installed only in test container to measure sink buffers/stats.
Weston log identifies libweston-14, GL ES 3.1, Mesa 25.0.7-2+deb13u1,
Mali-G610 (Panfrost). No llvmpipe fallback in this session.

| Decoder/output | Sink buffers | Rendered | Sink drops | Duration |
| --- | ---: | ---: | ---: | ---: |
| v4l2slh264dec / fakesink synchronized | 443 | 443 | 0 | 14.928 s |
| v4l2slh264dec / direct Wayland DMA-BUF NV12 | 443 | 443 | 0 | 14.943 s |
| v4l2slh264dec / forced BGRx conversion | 367 | 366 | 1 | 14.971 s |
| v4l2slvideo1h264dec / direct Wayland DMA-BUF NV12 | 443 | 443 | 0 | 14.924 s |
| avdec_h264 / Wayland I420 | 443 | 443 | 0 | 14.934 s |

All reached EOS. User confirmed continuous visible motion during these
comparisons. This confirms short physical playback, not long-run Miracast.
BGRx conversion loses frames upstream of the sink too: sink drops alone
understate the loss. Direct decoder-to-Wayland handoff is the preferred
candidate; no forced RGB conversion. Factory mapping in this environment:
v4l2slh264dec uses /dev/video3 (Hantro), additional v4l2slvideo1h264dec uses
rkvdec /dev/video1. Device/factory names must not be hardcoded generically.

Wayland emits gst_wl_window_ensure_fullscreen assertion 'self' on startup;
playback proceeds. Track separately; do not claim a warning-free result.
No pure Xorg test performed. Prior VLC/XWayland test is not a pure X11 test.

Diagnostic script: experiments/profile-g/live-test/replay-display.py.
It measures buffers arriving at the sink, not presentation feedback for every
physical HDMI refresh. Reuses private local /state/encoder-va-actual.ts.

A/V replay with two-second compressed queue ceilings, pulsesink async=false,
sync=true, buffer-time=200000, latency-time=20000: both provide-clock=true and
false delivered 443/443 video buffers, zero sink drops, EOS in 14.960/14.957 s.
Pulse sink input confirmed 48 kHz stereo. Audible quality/lip synchronization
not confirmed in this comparison; source may be silent. Queue ceiling does
not imply a forced two-second delay. Actual selected GstClock not recorded.
Next isolation: live RTP timestamp/jitter/demux behavior with this direct
hardware path; file replay does not exercise RTP jitter or its clock mapping.
No production defaults changed; normal kiosk/AP recovery invoked.

### Live RTP failure isolated, 2026-09-28 19:07–19:13 CEST

User repeatedly confirms no moving picture at ROCK. Instrumented player
uses direct v4l2slh264dec -> waylandsink, 200ms jitter/demux and 2s queue
ceilings. Both multiqueue and subsequent independent compressed queues stall
after one video buffer at parser/decoder/sink, while audio PTS advances with
running time and thousands of RTP buffers continue arriving. Disabling sink
sync at runtime did not recover video. These are failed trials, not accepted
receiver settings. No main/default changes.

Independent 15s pcap from the failed independent-queue trial contains 5648
RTP packets, no sequence breaks. FFmpeg decodes 443 frames, 442 unique,
maximum identical run 2, no stderr decode errors. This directly confirms
moving compressed video reached the receiver during its failed playback.
Do not conflate unrelated sender startup crashes with this successful transport.

Sender also crashed once with SIGSEGV and once with libpulse assertion
c->defer_event == e in connect_defer_cb. Later connection streamed with sender
running. Removing explicit PULSE_SERVER preceded that run, but does not prove
a fix. Test desktop release script failed to reliably approve the portal;
user had to approve manually. approve-test-share.py is an unaccepted UI helper,
NOT a background CLI implementation. Installed GND --help has no monitor/share
CLI options. Portal persist_mode/restore_token is the legitimate application
integration path to investigate, not an assumed existing GND feature:
https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html

Saved private local live-timing.{pcap,ts,framemd5,decode.log,log}; no captures
committed. Restored old live player, kiosk/AP and homebase after test.
Next: paced RTP replay from the captured packets, without another portal.

### Reproducer identifies demux pad replacement

Paced replay of the failed capture reproduces the failure without a sender or
portal. GStreamer tsdemux replaces video_0_1011 with video_1_1011 when activating
a new program/PMT including audio_1_1100. Static gst-launch delayed linking
keeps the old branch: new video pad repeatedly returns not-linked, audio can
continue. Hardware and software decode are downstream of this failure.
Video-only reproducer terminates with not-linked; A/V reproducer continues
with unlinked video, matching the live symptom.

Diagnostic pad-added handler links by caps to video/audio queues and unlinks
the previous video peer when the new stream pad arrives (which precedes old
pad removal). Local avdec_h264 paced replay: 441 video + 695 compressed audio
buffers, no error; all three stream pad links successful. This is a candidate
fix for the measured failure, not yet a production lifecycle implementation or
physical A/V acceptance. Does not establish the cause of earlier VLC freezes.

ROCK GStreamer 1.26.2 hardware confirmation: same paced RTP capture with
v4l2slh264dec and dynamic reconnection delivers 441 decoded video buffers and
695 compressed audio buffers to synchronized fakesinks, all pad links OK,
no bus error. Video count matches local software comparison. This verifies
reconnection through hardware decoding, NOT physical output or audio decoding.
Separate diagnostic image g-timing-diagnostic contains GI tooling; stopped
receiver-g-relink-probe after test. Kiosk continues running. Next acceptance
must use dynamic reconnection with real Wayland and decoded HDMI audio.

### Physical HDMI acceptance of corrected player with controlled A/V

Earlier live-timing.pcap desktop capture is mostly static and has silent audio
(mean/max -91 dBFS); user reported frozen/no tone. Frame hashes were insufficient
for visible motion acceptance. Do not label that HDMI trial passed.

Generated 1080p30 testsrc2 H264/AAC fixture with white flash and 880Hz tone pulse
for first 150ms of every second. Sent paced RTP MPEG-TS over LAN to ROCK:17236,
through corrected dynamic-link player, v4l2slh264dec -> direct waylandsink and
AAC -> pulsesink -> selected HDMI audio. User initially selected “Bild flüssig, Blitz und
Ton gleichzeitig”, but subsequently clarified they did NOT observe synchronization.
Only fluid picture and audible tone are confirmed; A/V synchronization remains
unverified. No bus error; video 835 sink buffers/834 rendered, zero sink
drops; audio 1313 buffers/1312 rendered. Fixed receiver timeout cut the trial
before all 900 fixture frames; these are not full-file completeness counts.

This passes short physical picture and audible-tone checks using controlled
LAN RTP, but does NOT establish A/V synchronization. It does not validate Wi-Fi Direct, portal automation, source desktop
capture, long-term playback, or exercise PMT replacement in this new fixture.
PMT replacement is separately verified by captured-stream software/hardware
replay above. Original ALSA false-wakeup warning remains a separate issue.
Restored kiosk/AP. No production/default/main/build change.

### Explicit synchronization retest, 2026-09-29

SSH key access restored by user using native VyOS CLI. Repeated 30-second
1080p30 flash/tone fixture over LAN RTP with corrected hardware player and
HDMI-A-1 output. Startup readiness confirmed before sending. Result: 897 video
buffers/rendered, 1368 decoded audio buffers/rendered, zero sink drops, no bus
error. No exact full-file accounting claimed (900-frame fixture, live RTP).
Asked user specifically whether beep leads/lags/matches flash; awaiting reply.
Synchronization remains UNVERIFIED until their answer. Kiosk/AP recovery invoked.

### Synchronization repeat explicitly accepted, 2026-09-29

User requested repeat and explicitly answered “Blitz und Ton gleichzeitig”
to the dedicated synchronization question during the 30-second HDMI trial.
Perceived A/V alignment is now confirmed for this short controlled LAN RTP
fixture, not a measured millisecond offset or long-term/live-Miracast guarantee.
Hardware decoder + direct Wayland + HDMI Pulse output: 897 video rendered,
1368 audio rendered, zero sink drops, no bus error. Log on ROCK:
/config/receiver/g-live-20260928/state/av-sync-repeat-20260929.log.
Normal kiosk/AP recovery invoked. Production integration and full Miracast
end-to-end acceptance remain outstanding; main unchanged.


## Integrated player regression (2026-09-29)

The Profile G player now uses Python GI instead of gst-launch delayed links.
It reconnects replacement tsdemux pad generations for the selected H.264/AAC
PIDs, including new-pad-before-old-removal ordering. Callback errors are
reported to the application loop. The container recipe includes Python GI and
GStreamer introspection. Decoder output stays native to waylandsink; no forced
BGRx conversion is introduced. Optional audio retains async=false.

23 automated tests passed, including real Gst pad replacement and protection
against an unrelated PID stealing the selected track. The integrated TrackLinks
implementation was additionally imported by a headless regression harness on
the ROCK: paced replay of live-timing.pcap through v4l2slh264dec produced 441
video buffers and 695 compressed audio buffers with no pipeline error. These
counters are not a new physical HDMI observation or an audio decode test.

The subsequent full Miracast attempt did not reach the player: the sender
waited for its P2P connection/socket, with no P2P group established on the ROCK.
On retry the exact receiver was discovered, but the AT-SPI selection helper did
not start streaming. Portal display approval succeeded; reliable receiver
activation remains unresolved. No full live Miracast acceptance is claimed.
The test used hardware decoder policy and 200 ms RTP jitter latency explicitly;
the CLI default remains unchanged. Kiosk/AP recovery was invoked after testing.
Evidence: production-relink-result.log and production-relink-live-receiver.log
in the ROCK test state directory, plus production-relink-live-sender.log in
the local test artifacts. Main, published images, and GitHub builds are unchanged.


### Live connection follow-up, 2026-09-29

Repeated P2P setup initially timed out before media. Running the sender UI with
GDK_BACKEND=x11 reached negotiation but then aborted with `XDP session streams
not found`; this UI experiment is not a receiver X11 playback test.

The live-only receiver session was changed to miracle-wifid --use-dev. A targeted
D-Bus Peer.Connect("pbc", "") for the known ThinkPad peer established the group,
DHCP and RTSP. This does not establish that --use-dev alone fixes automatic
acceptance. After restarting the sender with its normal Wayland UI, a fresh
connection reached STREAMING and the production player linked video_0_1011 and
audio_0_1100. /proc fd inspection as kiosk confirms /dev/video3 and /dev/media1
open (hardware decoder); HDMI ALSA PCM reports RUNNING. A 30-second flash/tone
clip was played on the actual captured ThinkPad screen, followed by a repeat.
Physical fluidity/sync feedback remains pending at this writing.

No generic auto-accept-all-peers logic was added. The targeted connection was
only to the user-authorized test ThinkPad. AT-SPI sometimes returns a 0,0 row
rectangle and does not provide reliable activation, so successful helper return
values still cannot be treated as streaming confirmation.

Upstream context (not proof of our root cause):
https://github.com/albfan/miraclecast/issues/232
https://github.com/albfan/miraclecast/issues/548


### Live HDMI A/V accepted after correcting sender audio routing

The first live clip played into the ThinkPad analog sink, whereas GND captured
its own virtual sink monitor (`gnome_network_displays_gnome-ne.monitor`). The
user correctly reported local sync but no ROCK audio; that first run failed.
The repeat explicitly set PULSE_SINK=gnome_network_displays_gnome-ne only for
ffplay (no system default change). Sender sink-input inspection confirmed the
clip routed to that virtual sink. On the ROCK, the player sink-input targeted
g_hdmi, unmuted; a four-second g_hdmi.monitor capture contained 374496 s16
samples, peak 3989 and RMS 1087.93, confirming nonzero received audio.

The user then explicitly reported: "der test war gut und synchron" and, in the
dedicated question, "Bild flüssig, Ton und Blitz gleichzeitig". This accepts
the short end-to-end live Miracast test with hardware decode and HDMI output.
It is not a quantified latency measurement or a long-duration stability test.

Working live configuration: Intel ThinkPad sender, native Wayland GND UI,
receiver wifid --use-dev, targeted known-peer PBC acceptance during setup,
GStreamer reconnectable tracks, hardware decoder (/dev/video3), 200 ms RTP
jitter setting, direct Wayland video and PulseAudio selected HDMI-A-1. The
--use-dev setting remains a live experiment, not a proven generic fix.
Reliable unattended pairing/portal startup and automatic application audio
routing remain separate integration tasks. Main and build artifacts unchanged.
Kiosk/AP recovery invoked after the accepted test.


### HDMI error audit after accepted live test, 2026-09-29

Kernel journal since 06:55 today contains no HDMI/codec/ASoC audio error.
The retained dmesg codec.8.auto prepare(-19) burst dates to Sep 28 17:47:17;
later retained HDMI I2C errors date to Sep 28 19:25:14, not today's live test.
Today's receiver selected only HDMI-A-1/plughw:1,0; HDMI-A-2 was disconnected.
Card1 is hdmi0-sound/fddf0000.i2s; card2 is hdmi1-sound/fddf4000.i2s. The
remaining PulseAudio false POLLOUT wakeup message explicitly names fddf0000,
therefore the active first HDMI path, not the unused second one. It occurred
in the accepted run and must not be reported as fixed or as renewed HDMI2
probing. Existing EDID/ELD selection and private PulseAudio configuration
already avoid opening every ALSA card. No speculative driver change or
blanket disabling of HDMI2 was made.


### Targeted HDMI audio scheduling A/B, 2026-09-29

Two isolated PulseAudio instances were tested sequentially against only
plughw:1,0, keeping kiosk running and HDMI2 closed. Each used the same GStreamer
pulsesink settings (200 ms buffer, 20 ms latency) as the player. Thirty seconds
of continuous digital silence passed with tsched=0 and tsched=1, neither
logging a false wakeup or underrun. Ten short stream start/stop cycles per mode
then reproduced one false POLLOUT wakeup with tsched=0, versus zero with
tsched=1. All twenty streams exited successfully; no underruns were logged.
The timer mode was actually enabled (mmap+timer), though the driver reported
that period wakeups could not be disabled. Configured hardware ring sizes
differed (4800 vs 96000 frames); that is capacity, not measured presentation
latency. PulseAudio reported negotiated final latency 240 vs 200 ms.

Live-only hdmi-audio.py was changed to tsched=1 for a controlled LAN RTP
flash/tone replay using v4l2slh264dec and direct Wayland output. An initial
launcher failed because the supplemental group list was empty; it was corrected
by deriving group IDs from device nodes and the replay was restarted. The
subsequent run rendered 837 video and 1323 audio buffers, zero sink-reported
drops and no pipeline error. This is not full fixture accounting: startup
timing was not aligned to READY, so it must not be presented as 900/900 frames.
No false wakeup or new HDMI codec kernel error appeared in that run. Physical
A/V synchronization feedback for this new scheduling variant is pending.

The live-only change was reverted after this comparison; kiosk/AP recovery
was invoked. No tsched default was changed in source or main. This is a
promising candidate, not a proven elimination of the driver warning. Evidence:
audio-scheduling-ab.json, audio-cycles-ab.json, their per-mode PulseAudio logs,
tsched1-av-test.log and tsched1-av-container.log in the ROCK state directory.


### Timer scheduling accepted and integrated, 2026-09-29

The user could not observe the first tsched=1 A/V replay, so it was repeated
with a 90-second three-loop fixture. This time the harness waited for READY
before the RTP sender started. The user explicitly confirmed "Ja, flüssig und
synchron". tsched=1 is now integrated into Profile G's private HDMI PulseAudio
sink only. EDID/ELD output selection and the silence fallback are unchanged;
main and Profile F are untouched. This is a validated mitigation candidate
for the reproduced false-wakeup warning, not a long-term driver fix claim.


The accepted 90-second tsched=1 repeat finished with 2697 rendered video
buffers and 4184 rendered audio buffers, zero sink-reported drops, no pipeline
error and no false-wakeup message in its container log. The user nevertheless
saw a start warning identified as hdmi-audio-codec/ALSA. Auditing the complete
system journal for the current test and dmesg after restoring kiosk found no
new matching event. The newest retained hdmi-audio-codec event is actually
Sep 28 19:25:14: codec.7.auto "HDMI: Unknown ELD version 0"; the repeated
codec.8.auto prepare(-19) burst is Sep 28 17:47:17. Thus the earlier note only
described the error(-19) burst, not the newest codec message of every type.
Previously printed console text becoming visible during VT/display takeover
is a plausible explanation, not visually proven. Do not describe the user's
observed start warning as definitively solved. Kiosk and AP verified active
after cleanup; tsched=1 retained in Profile G source/test context only.


## Miracast restart checks and Moonlight receiver, 2026-09-29

Miracast restart acceptance FAILED: two GND 0.99.0 launches on ThinkPad aborted
with libpulse socket-client.c connect_defer_cb assertion c->defer_event == e.
A third launch using an explicit PULSE_SERVER Unix socket passed this stage,
but Intel 8265 firmware failed during P2P setup (iwlwifi device error/reprobe,
firmware 36.c8e8e144.0) and NetworkManager P2P reason 71. This does not invalidate
the previously accepted short live A/V test; it blocks reliable-start claims.
Recovery restored the ROCK kiosk/AP. Sender regression journal is saved locally
as miracast-start-regression.log. No workaround is claimed as a generic fix.

Moonlight receiver: switched actual Profile G config to method=moonlight, host
ThinkPad LAN, Desktop app, H.264, 1920x1080, 30fps, 10000 Kbps, decoder=auto.
ThinkPad Sunshine 2026.914.233613 used Intel h264_vaapi. Pairing used Sunshine's
stdin PIN mode and Moonlight --pin; existing credentials were not reset. ROCK
identity lives in /state/config. A first incomplete pairing was cleared by
restarting the temporary Sunshine process; subsequent pairing/stream succeeded.

ROCK Moonlight 6.1.0 auto decoder could not initialize VAAPI/VDPAU/v4l2m2m and
fell back to FFmpeg software H.264 decoding with SDL rendering. This is not
the GStreamer stateless hardware decoder used by Miracast, and must not be
reported as hardware-decoded. One container CPU snapshot was ~93% (roughly
one CPU core), not a performance benchmark.

The actual captured ThinkPad desktop played the flash/tone clip, explicitly
routed to Sunshine's virtual stereo sink. User confirmed "Bild flüssig, Ton
und Blitz synchron" on ROCK HDMI. Sunshine also selected its virtual audio
sink automatically on connection. AP remained active throughout Moonlight.
After restoring kiosk/AP, the test container was recreated from the same
persistent state: stream resumed without a new PIN, 1080p30 video and stereo
audio started, HDMI-A-1 selected. A four-second HDMI monitor capture contained
382170 samples with peak 8986, confirming nonzero audio after reconnection.
This second run has log/monitor evidence, not a second independent visual
user acceptance. The final recovery restored kiosk/AP and the temporary
Sunshine sender was stopped. Evidence on ROCK: moonlight-h264-1080p30.log and
moonlight-reconnect-1080p30.log. Main and build images unchanged.

Remaining: Miracast sender/start stability; user-facing automatic application
audio routing for GND; Moonlight hardware decoder integration and 60fps/latency
comparison; longer playback tests. No new HDMI codec errors were found in the
kernel journal during these tests.


### Moonlight 1080p60 software baseline, 2026-09-29

The 60fps run used a newly generated 1920x1080p60 flash/tone fixture rather
than duplicating the existing 30fps source. Moonlight requested H.264/60fps,
10Mbps over LAN; Sunshine used the existing Intel encoder. The concurrent
FFmpeg build container was paused during playback to avoid CPU contention.
The user explicitly confirmed fluid video and synchronous tone/flash.
Container CPU samples while the fixture moved were 145–154% (one fully busy
core corresponds to 100%); this includes Weston/audio and is not a decoder
benchmark. A four-second HDMI monitor capture had 382284 s16 samples with
peak 5324. These are a short user acceptance and audio-presence evidence,
not a measured end-to-end latency or proof of 60 unique frames displayed.
Kiosk/AP recovery performed afterwards. Evidence: moonlight-software60.log
on ROCK and moonlight-software60-audio.raw in the local live-test directory.

A private FFmpeg 7.1 V4L2-request build is being evaluated for Moonlight only.
Source: jernejsk/FFmpeg, commit 904a85173fab816bb3c30652300efa93f2333657
(branch v4l2-request-n7.1). Moonlight's existing DRM-PRIME renderer includes
support for out-of-tree hwaccels. The original distro libraries and receiver
image remain unchanged; test libraries use a private bind mount and
LD_LIBRARY_PATH. No production hardware-decoding acceptance yet.


### Moonlight Hantro/DRM PRIME hardware probe accepted, 2026-09-29

The private FFmpeg build completed successfully. Its source archive SHA256
is 122cffb7b070c68e37bd4890cd7b52d671f7f6ba7ad69885e0e64d5ab6667996.
Moonlight loaded libavcodec61/libavutil59/libswscale8 from the private prefix.
Forced hardware H.264 at 1080p60 selected h264_v4l2request, hantro-vpu,
DRM PRIME and EGL/GLES rendering under Weston/Wayland/Panthor. The real
stream reconfigured to 1920x1088; Moonlight held /dev/media1, /dev/video3
and renderD128 FDs. The user confirmed correct picture/colors, fluid motion
and synchronous flash/tone. Container CPU samples during the same real
60fps fixture were 44.60–48.95%, versus 145–154% software: about two thirds
lower whole-receiver CPU usage, not a standalone decoder benchmark.

After complete container recreation, a 1080p30 hardware stream reconnected
without PIN, using the same Hantro/DRM PRIME path and receiving video/audio.
CPU samples were approximately 40–46%. This 30fps restart has log evidence,
not a separate visual acceptance. No new HDMI codec/I2C kernel errors were
found in the test window. Both hardware logs still contain seatd errors for
unmapped input/event2 and event3 and priority-elevation warnings; do not
claim all startup warnings are solved. Display/audio acceptance is separate
from local input-device handling.

Kiosk and AP restored active; receiver stopped; temporary ThinkPad Sunshine
stopped and analog default audio restored. 23 existing Profile G tests pass.
The private diagnostic libraries remain optional on the live system. They
are not integrated into the image/main. For reproducible settings and
production caveats see live-test/MOONLIGHT-HARDWARE.md.


### AirPlay live user acceptance, 2026-09-29

User accepted the AirPlay part of Profile G after testing an iPhone on
VyOS-AP: Photos video with very good picture quality and audio, full iPhone
screen mirroring, and YouTube in the browser. Small subjective latency was
acceptable; no end-to-end latency or objective A/V offset measurement was
made. UxPlay 1.74 used v4l2slh264dec, Wayland and the private HDMI Pulse sink.
PIN pairing and subsequent receiver recreation retained the client register.
The reported video-test exit at 10:29:31 was the five-minute recovery timer,
not an observed crash. Later trials used a fifteen-minute recovery timer.

A live comparison replaced `-vs "waylandsink fullscreen=true"` with
`-vs waylandsink -fs`. User reported no visible change in borders; both
forms still emitted gst_wl_window_ensure_fullscreen assertion warnings.
Fullscreen with preserved aspect ratio remains the intended TV default.
No automatic cropping/stretching is accepted or implemented. The precise
source of the four-sided browser-video borders was not measured; nested
letterboxing remains a hypothesis. Do not claim -fs fixes this issue.

Apple TV protected content produced audio only, consistent with UxPlay's
documented lack of support for Apple video DRM. This limitation is part of
the accepted scope, not a passed protected-video test. Direct YouTube app
HLS (-hls) was not enabled or tested; user deferred it. Long-duration tests,
startup-warning cleanup, and repeating acceptance on the final SD/ISO remain
outstanding. Acceptance applies to live tested AirPlay functionality, not
all G methods or full-image release qualification.

Temporary live session changes (line-buffered logging, a fixed test PIN,
and -fs comparison) are not production defaults and are not included in
the current build. Do not carry the fixed diagnostic PIN into production.
