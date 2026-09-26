# Main/profile D audit and live checks, 2026-09-26

Fetched origin/main: 13cf40e8de8cf18022dc607060690d8b8b2c1fa8.
Recent commits record rolling dispatches. Last code fix fd7153a preserves image
names in tables. Watcher checks out main, cron 23,53 each hour. Latest ROCK
candidate run 36110489698 succeeded with network=true, kvm=false: not D evidence.
45 tests passed from an isolated archive of current main: profile(8), video
supervisor(9), hardware provider(10), CLI(9), capture(9).

Main already has MPP H264, GStreamer and optional V4L2 RGA conversion in D.
Main media build pins match installed MPP/FFmpeg/GStreamer source metadata.
The main vs F media builder delta is only removal of grep -q from two pipefail
pipelines; experimental lifecycle/colorimetry patches are not applied there.
No main changes, push, workflow dispatch or new image build in this review.

Live host: kernel 6.18.50-vyos, installed wayland image, not a pristine main
kernel. HDMI-RX reports Link has been severed; no actual HDMI capture/remote
browser, input latency or end-to-end color qualification can be claimed.
D video service inactive before/after. Kiosk kept running. No module reload.

Existing RGA experimental_full_csc was N. Separate recovery timers protected
short toggles to Y, then restored N. BGR/RGB solid-red conversions with BT601
and BT709 compared to GStreamer software conversion. Max error before: 1 for
601, 8 for 709. With candidate: 1 in all four cases (NV12M negotiation).
These do not replace prior larger full-range/random-color tests.

Installed FFmpeg-rockchip encoded H264 and HEVC: 120 decoded frames each,
1920x1080, BT709/tv signaled. No new FFmpeg lifecycle-patch test here.
Installed GStreamer MPP encoded H264:120 frames; color metadata absent.
Combined candidate RGA -> installed MPP H264:300 frames decoded at1080p;
color metadata still absent. Candidate GStreamer colorimetry plugin was not
available on this freshly installed system and was not rebuilt in this review;
its prior 12-case evidence remains in the parent directory, not a new result.

Recommendation: narrowly port revision-gated RGA + explicit negotiated color
metadata as opt-in D additions, retaining software conversion and old paths.
Do not merge all of F. Test the rebuilt patched plugin and complete HDMI/client
chain before changing defaults. FFmpeg EOS/ownership patches need separate
D repeated-start/stop/EOS regression; synthetic baseline success does not prove
their value or integration. H264 remains default; HEVC is client-dependent.
No Chromium/Wayland/AV1 decoder dependency is needed for ordinary D sender.
A/B should not gain these media dependencies; constrain provider/profile gating.
