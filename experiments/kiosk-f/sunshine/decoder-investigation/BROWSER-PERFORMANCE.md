# Isolated hardware browser comparison

Generate fixtures with `bash make-performance-fixtures.sh NEW_DIRECTORY` on a
machine with libx264/libx265 FFmpeg. Both use testsrc2, 1920x1080, 60fps, 30s,
8Mbps target/max bitrate, 8Mbps VBV buffer, B-frames, BT709 limited, 8bit420.
This is a decoding workload comparison at the same target bitrate, not a
measurement of equal visual quality or compression savings.

On the test host, identify the actual decoder video/media graph. Run:

```
bash test-browser-performance.sh IMAGE FIXTURE_DIRECTORY NEW_RESULTS /dev/videoN /dev/mediaN
python3 summarize-browser-performance.py RESULTS_DIRECTORY
```

The image needs Chromium, Python and Weston. This reuses the isolated GL
Wayland test path, retains Chromium sandbox, exposes selected devices, limits
container memory to1GiB, uses network none plus internal loopback HTTP, and
removes each container. The existing physical kiosk is not changed.

Three runs each, alternating order. Probe reads container cgroup cpu.stat every
~0.5s; summary discards first five seconds of observed playback and ends at the
last playing sample. CPU includes Chromium, Weston and the probe, not only the
hardware decoder. 100% means one logical CPU core. Dynamic frequency governors
remain unchanged; this is not an isolated laboratory benchmark. JSON retains
Media decoder/platform diagnostics, frame counts, elapsed playback time and CPU
samples. Codec performance cannot be inferred solely from canPlayType or flags.

Require ended, correct dimensions/frame count, V4L2VideoDecoder and platform=true
before calling a run hardware playback. Frame drops include startup; real display
smoothness and input/stream latency require separate physical/Moonlight tests.
The recorded 30s elapsed time is playback duration, not decoding latency.

Controlled fallback: set PROBE_OMIT_DECODER=1 with test-browser-wayland.sh to
omit the explicit V4L2 video/media nodes while retaining the graphics device.
This is only a V4L2 absence test, not a generic ban on all hardware decoders.
Check Media diagnostics to establish the backend actually selected.
