# Isolated MediaMTX → Chromium WebRTC, test3

The earlier software-only capability result remains valid, but does not apply
to the now working V4L2/Mali browser path. Chromium153 with these devices/flags
advertises HEVC receive support. Initial real WHEP tests pass both H264 and HEVC
using MediaMTX1.20.0, same test3 kernel and isolated Weston browser image.

Two short trials per codec so far, synthetic1080p60/8Mbps/noBframes. RTP input
stats report60fps, zero packetsLost/framesDropped, and >700 / >1100 decoded
frames respectively. Browser logs select V4L2 stateless S264/S265. The longer
trial restricts the offer to H264 High or HEVC Main1 to match actual fixtures.
H264 average totalDecodeTime/framesDecoded ~4.06ms; HEVC ~2.82ms. These are
receiver-reported decoder times for these streams, not end-to-end/input latency
and not a universal codec comparison. HTML-video dropped-frame counters remain
high in the headless renderer, separately from RTP framesDropped=0; physical
presentation and the BT709 native-import color issue remain open.

The publisher uses the existing optional D FFmpeg image only for stream copy;
this does not test live HDMI capture or the full production D pipeline. No
installed service, FFmpeg, plugin, firewall policy or public stream is replaced.
Receiver is the ROCK's isolated Chromium, not the ThinkPad. Keep H264 default for
clients without validated HEVC receive support. Main10 is advertised but untested.

## Reproduce

Generate synthetic fixtures locally:

```
bash make-fixtures.sh NEW_FIXTURE_DIRECTORY
```

Copy that directory and this repository's experiment scripts to the test host.
Identify actual decoder video/media nodes through the media graph. Then run:

```
bash test-webrtc.sh FIXTURES NEW_RESULTS BROWSER_IMAGE FFMPEG_IMAGE /dev/videoN /dev/mediaN /usr/local/bin/mediamtx
```

BROWSER_IMAGE needs Chromium/Python/Weston and the kiosk account. FFMPEG_IMAGE
must have FFmpeg as its entrypoint with raw H264/HEVC demuxers, RTSP/TCP muxing.
Validated images are the same browser-wayland-test3 image as F and D runtime
1ec163bc98c45a9c1baf29a5e53e1e442e7a76669d98650b2760ddffc3401683.
The shared probe helpers remain under experiments/kiosk-f/sunshine/decoder-investigation.

Each browser is nonroot/sandboxed,1GiB bound; publisher256MiB. A temporary internal
Podman network provides an interface for ICE gathering, with no external network
route. Publisher joins browser network namespace; no host ports are published.
MediaMTX RTSP/WHEP bind loopback, ICE UDP uses the private namespace. MoQ/RTMP/HLS/
SRT disabled only in the test config. Containers are removed in dependency order
before the network; INT/TERM cleanup is armed. Put an outer180s systemd/timeout
bound around a run. Existing production D/F services remain running throughout.

## Setup failures retained as limitations

- Minimal FFmpeg image lacks MP4 demuxer: use raw AnnexB fixture.
- Raw demuxer cannot stream_loop seek: repeat complete IDR-starting fixture bytes
  beforehand; FFmpeg generates continuous input timestamps with -r60.
- MediaMTX's default MoQ tried creating TLS files in read-only working directory:
  explicitly disable MoQ for this WHEP-only test.
- network=none produced SDP success but no ICE/video: require actual decoded
  frames, not HTTP success. Internal isolated network supplies ICE interface.
- Containers sharing a network namespace must be removed sequentially; a single
  rm of both produced a dependency race. Corrected runner validates final frames.

Record only synthetic/technical evidence in Git. Do not publish real HDMI captures
or raw SDP credentials. Saved page evidence includes only codec SDP lines/stats.

Final parameterized runner repeated successfully (serviceexit0): H2641184
decoded frames/2 RTP framesDropped, reported61fps at sampling; HEVC1156frames/0
dropped,60fps. Average decoder times4.03ms/2.85ms. This is a short local test,
not proof of loss-free sustained operation. All temporary containers/network
removed; production D/F active. No new kernel errors recorded during tests.
