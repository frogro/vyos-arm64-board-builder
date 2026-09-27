# Profile D HDMI media integration check, 2026-09-26

Base main: 13cf40e8de8cf18022dc607060690d8b8b2c1fa8. Isolated integration
branch from main; no profile F, browser/kernel decoder patchset or kiosk image.
Host test kernel 6.18.50-vyos is the existing F-capable live kernel, not the
result of this new A-D build. A new image still needs boot/update verification.

HDMI-RX detected 1920x1080 at60Hz. Installed FFmpeg MPP H264 and HEVC each encoded
180 frames, decoded successfully, BT709/tv metadata. Installed GStreamer with
corrected RGA also encoded180 frames, but lacked color metadata.

Rebuilt the optional GStreamer patch on ARM64 in a disposable Debian Bookworm
container against the exact installed MPP shared library and pinned MPP headers.
Private plugin folder/registry only; no host plugin/binary replacement.
12 synthetic checks (codec H264/HEVC, BT601limited/BT709limited/BT709full,
option off/on) passed. Then actual HDMI -> RGA NV12M -> patched MPP:
3 H264 and3 HEVC runs,180 frames each, all decoded at1080p with BT709 matrix,
primaries, transfer, and limited-range VUI. No actual-screen recording in Git.

Isolated loopback MediaMTX1.20 + software/headless sandboxed Chromium153:
HDMI/RGA/MPP H264 received through WHEP/WebRTC for15s. Connected,881 decoded
frames,0 RTP packets lost. Page playback counter reports108 dropped frames;
inbound RTP reports11 dropped frames. This is a function check on the same
ROCK, not an external receiver, 60fps presentation guarantee, or latency test.
The first harness run attempted RTSP before readiness; repeating after waiting
for startup passed. Production supervisor already waits for local transport.

RGA candidate uses the same tested enabled-path code, consolidated into one
provider patch. Unlike the experimental patch stack, its disabled path retains
the original BT601 selector. Applied to pristine6.18.50 RGA sources and compiled
as an external ARM64 module against prepared matching6.18.50 headers. This
compile artifact was NOT loaded on the host; the already installed, matching
kernel's opt-in path was used for live tests. No unsafe ABI module replacement.

All eight KVM Python test files and selection test passed after integration,
including new CLI default/validation and converter-fallback cases. Recovery
timers protected the temporary RGA flag; restored N. D service remained inactive
as found, Kiosk stayed active, no failed units after cleanup.

No FFmpeg ownership/EOS changes are included: those need their own failure and
repeated-start regression. No H265 default switch. The media build's two grep-q
pipefail/SIGPIPE hazards are corrected without changing the encoder source.
